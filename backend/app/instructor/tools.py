"""Explicit internal API tools; no arbitrary HTTP, shell, SQL or outbound messaging."""
import re
from typing import Annotated
from urllib.parse import quote
import httpx
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

# name, method, route, human review required. Every write requires confirmation;
# decisions additionally require a standalone plan with the current record shown.
SPECS = [
    ('courses', 'GET', '/api/v1/catalog/courses', False),
    ('course', 'GET', '/api/v1/catalog/courses/{course_id}', False),
    ('staff_courses', 'GET', '/api/v1/catalog/staff/courses', False),
    ('course_history', 'GET', '/api/v1/catalog/staff/courses/{course_id}/history', False),
    ('uploads', 'GET', '/api/v1/catalog/uploads', False),
    ('upload', 'GET', '/api/v1/catalog/uploads/{upload_id}', False),
    ('extract_metadata', 'POST', '/api/v1/catalog/uploads/{upload_id}/extract-metadata', False),
    ('reject_upload', 'POST', '/api/v1/catalog/uploads/{upload_id}/reject', True),
    ('approve_course', 'POST', '/api/v1/catalog/uploads/{upload_id}/approve', True),
    ('publish_course', 'POST', '/api/v1/catalog/staff/courses/{course_id}/publish', True),
    ('withdraw_course', 'POST', '/api/v1/catalog/staff/courses/{course_id}/withdraw', True),
    ('refresh_course_index', 'POST', '/api/v1/catalog/staff/courses/{course_id}/refresh-index', True),
    ('templates', 'GET', '/api/v1/documents/templates', False),
    ('approve_template', 'POST', '/api/v1/documents/templates/{template_id}/approve', True),
    ('documents', 'GET', '/api/v1/documents', False),
    ('document', 'GET', '/api/v1/documents/{artifact_id}', False),
    ('generate_document', 'POST', '/api/v1/documents', False),
    ('review_document', 'POST', '/api/v1/documents/{artifact_id}/review', True),
    ('download_document', 'GET', '/api/v1/documents/{artifact_id}/download/{fmt}', False),
    ('curricula', 'GET', '/api/v1/curriculum', False),
    ('curriculum', 'GET', '/api/v1/curriculum/{curriculum_id}', False),
    ('research_curriculum', 'POST', '/api/v1/curriculum/research', False),
    ('generate_curriculum', 'POST', '/api/v1/curriculum', False),
    ('revise_curriculum', 'POST', '/api/v1/curriculum/{curriculum_id}/revise', False),
    ('submit_curriculum', 'POST', '/api/v1/curriculum/{curriculum_id}/submit', False),
    ('review_curriculum', 'POST', '/api/v1/curriculum/{curriculum_id}/review', True),
    ('align_curriculum', 'POST', '/api/v1/curriculum/{curriculum_id}/alignment', False),
    ('download_curriculum', 'GET', '/api/v1/curriculum/{curriculum_id}/pdf', False),
    ('frameworks', 'GET', '/api/v1/curriculum/frameworks', False),
    ('framework', 'GET', '/api/v1/curriculum/frameworks/{framework_id}', False),
    ('approve_framework', 'POST', '/api/v1/curriculum/frameworks/{framework_id}/approve', True),
    ('campaigns', 'GET', '/api/v1/marketing', False),
    ('campaign', 'GET', '/api/v1/marketing/{campaign_id}', False),
    ('generate_campaign', 'POST', '/api/v1/marketing', False),
    ('review_campaign', 'POST', '/api/v1/marketing/{campaign_id}/review', True),
    ('export_campaign', 'GET', '/api/v1/marketing/{campaign_id}/export', False),
    ('opportunities', 'GET', '/api/v1/rfp/opportunities', False),
    ('opportunity', 'GET', '/api/v1/rfp/opportunities/{opp_id}', False),
    ('opportunity_history', 'GET', '/api/v1/rfp/opportunities/{opp_id}/history', False),
    ('update_opportunity', 'PATCH', '/api/v1/rfp/opportunities/{opp_id}', False),
    ('import_opportunities', 'POST', '/api/v1/rfp/import', False),
    ('search_opportunities', 'POST', '/api/v1/rfp/run', False),
    ('rfp_activity', 'GET', '/api/v1/rfp/activity', False),
    ('answer_course_question', 'POST', '/api/v1/chat', False),
]
TOOLS = {name: {'name': name, 'method': method, 'path': path, 'decision': decision}
         for name, method, path, decision in SPECS}
IDENTITY_FIELDS = {'reviewer', 'reviewer_name', 'requester'}


def route_for(app, tool):
    def routes(router):
        for route in router.routes:
            nested = getattr(route, 'original_router', None)
            if nested is not None:
                yield from routes(nested)
            else:
                yield route
    return next(r for r in routes(app) if getattr(r, 'path', '') == tool['path']
                and tool['method'] in getattr(r, 'methods', set()))


def definitions(app):
    """Use the existing request models as the single source of tool parameters."""
    result = []
    for tool in TOOLS.values():
        route = route_for(app, tool)
        item = {**tool, 'parameters': {}}
        for group, fields in [('path', route.dependant.path_params), ('query', route.dependant.query_params)]:
            item['parameters'][group] = {f.name: {
                'required': f.field_info.is_required(),
                'schema': TypeAdapter(Annotated[f.field_info.annotation, f.field_info]).json_schema()
            } for f in fields}
        if route.body_field:
            item['parameters']['body'] = TypeAdapter(route.body_field.field_info.annotation).json_schema()
        result.append(item)
    return result


def planner_definitions(app):
    """Compact input signatures; full service validation still runs server-side."""
    def shape(node, defs):
        if '$ref' in node:
            return shape(defs[node['$ref'].split('/')[-1]], defs)
        if 'anyOf' in node:
            return [shape(part, defs) for part in node['anyOf']]
        if node.get('type') == 'object':
            return {'fields': {k: shape(v, defs) for k, v in node.get('properties', {}).items()},
                    'required': node.get('required', [])}
        if node.get('type') == 'array':
            return {'list': shape(node.get('items', {}), defs)}
        return {k: v for k, v in node.items() if k in ('type', 'enum', 'default', 'const')}
    result = []
    for tool in definitions(app):
        params = tool['parameters']
        result.append({'tool': tool['name'], 'write': tool['method'] != 'GET', 'decision': tool['decision'],
            'path': {k: shape(v['schema'], {}) for k, v in params['path'].items()},
            'query': {k: shape(v['schema'], {}) for k, v in params['query'].items()},
            'body': shape(params.get('body', {}), params.get('body', {}).get('$defs', {}))})
    return result


def validate_call(app, call, reviewer):
    if call.tool not in TOOLS:
        raise HTTPException(422, 'Unsupported instructor tool')
    tool = TOOLS[call.tool]
    route = route_for(app, tool)
    for group, fields in [('path', route.dependant.path_params), ('query', route.dependant.query_params)]:
        values = getattr(call, group)
        if set(values) - {f.name for f in fields}:
            raise HTTPException(422, f'Unexpected {group} parameters')
        for field in fields:
            if field.name not in values:
                if field.field_info.is_required():
                    raise HTTPException(422, f'Missing {group} parameter: {field.name}')
                continue
            try:
                TypeAdapter(Annotated[field.field_info.annotation, field.field_info]).validate_python(values[field.name])
            except ValidationError:
                raise HTTPException(422, f'Invalid {group} parameter: {field.name}') from None
        if group == 'path' and any(not re.fullmatch(r'[\w.-]{1,80}', str(v)) or str(v) in {'.', '..'} for v in values.values()):
            raise HTTPException(422, 'Invalid record identifier')
    if route.body_field:
        annotation = route.body_field.field_info.annotation
        if isinstance(call.body, dict):
            for name in IDENTITY_FIELDS & annotation.model_fields.keys():
                call.body[name] = reviewer
        if call.tool == 'search_opportunities':
            if call.body.get('notify'):
                raise HTTPException(422, 'Instructor chat cannot send email or webhooks')
            call.body['notify'] = False
        try:
            call.body = TypeAdapter(annotation).validate_python(call.body).model_dump(mode='json', exclude_unset=True)
        except ValidationError as exc:
            # No raw input or provider strings in validation errors.
            errors = '; '.join('.'.join(map(str, e['loc'])) + ': ' + e['msg'] for e in exc.errors(include_input=False))
            raise HTTPException(422, 'Invalid action parameters: ' + errors) from None
    elif call.body:
        raise HTTPException(422, 'This tool does not accept a body')
    if call.tool == 'download_document' and call.path.get('fmt') not in ('pdf', 'docx'):
        raise HTTPException(422, 'Choose PDF or DOCX')
    return call


def url_for(call):
    path = TOOLS[call.tool]['path']
    for key, value in call.path.items():
        path = path.replace('{' + key + '}', quote(str(value), safe=''))
    return path


async def invoke(app, key, call):
    tool = TOOLS[call.tool]
    # ASGI transport cannot leave this process. Existing endpoint auth, request
    # validation, source checks, approval gates and audit events all run normally.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                 base_url='http://rex.internal') as client:
        response = await client.request(tool['method'], url_for(call), params=call.query,
            json=call.body if route_for(app, tool).body_field else None,
            headers={'X-API-Key': key})
    if response.status_code >= 400:
        try:
            detail = response.json().get('detail', 'Action failed')
        except ValueError:
            detail = 'Action could not complete; inspect the agent page before retrying'
        raise HTTPException(response.status_code, detail)
    if call.tool in {'download_document', 'download_curriculum', 'export_campaign'}:
        return {'download_path': url_for(call), 'media_type': response.headers.get('content-type'),
                'notice': 'Download is authenticated and rechecks current source and review eligibility.'}
    return response.json()
