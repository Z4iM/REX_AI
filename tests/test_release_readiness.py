"""Cross-workflow release checks that need no provider credentials."""
from io import BytesIO
import zipfile
import pytest
from backend.app.ingestion import archive_safety


def office_zip(entries):
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return stream.getvalue()


def test_health_and_openapi_report_same_release(catalog_client):
    assert catalog_client.get('/health').json()['version'] == catalog_client.get('/openapi.json').json()['info']['version']


def test_every_staff_workspace_route_requires_authentication(catalog_client):
    schema = catalog_client.get('/openapi.json').json()
    count = 0
    prefixes = tuple('/api/v1/' + name for name in ('documents', 'curriculum', 'marketing', 'rfp', 'instructor', 'demo', 'catalog/uploads', 'catalog/staff'))
    for path, operations in schema['paths'].items():
        if not path.startswith(prefixes):
            continue
        for method, operation in operations.items():
            if method not in {'get', 'post', 'put', 'patch', 'delete'}:
                continue
            url = path
            for parameter in operation.get('parameters', []):
                if parameter['in'] == 'path':
                    value = '1' if parameter['schema'].get('type') == 'integer' else 'test'
                    url = url.replace('{' + parameter['name'] + '}', value)
            response = catalog_client.request(method, url, json={})
            assert response.status_code == 401, (method, path, response.text)
            count += 1
    assert count >= 50


def test_docx_expansion_limit_fails_before_parsing(catalog_client, staff_headers, monkeypatch):
    monkeypatch.setattr(archive_safety, 'MAX_EXPANDED_BYTES', 500)
    raw = office_zip({'[Content_Types].xml': '<Types/>', 'word/document.xml': 'a' * 1000})
    assert len(raw) < 500
    response = catalog_client.post('/api/v1/catalog/uploads', headers=staff_headers,
                                   files={'file': ('compressed.docx', raw)})
    assert response.status_code == 422
    assert 'expanded content limit' in response.json()['detail']
    assert catalog_client.get('/api/v1/catalog/uploads', headers=staff_headers).json()['count'] == 0


def test_incomplete_docx_package_is_validation_error(catalog_client, staff_headers):
    raw = office_zip({'[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'})
    response = catalog_client.post('/api/v1/catalog/uploads', headers=staff_headers,
                                   files={'file': ('incomplete.docx', raw)})
    assert response.status_code == 422


def test_xlsx_expansion_limit_is_enforced(monkeypatch):
    from backend.app.agents.rfp.sources import parse_upload
    monkeypatch.setattr(archive_safety, 'MAX_EXPANDED_BYTES', 500)
    raw = office_zip({'[Content_Types].xml': '<Types/>', 'xl/workbook.xml': 'a' * 1000})
    with pytest.raises(ValueError, match='expanded content limit'):
        parse_upload('compressed.xlsx', raw)


def test_incomplete_xlsx_has_a_user_facing_import_error():
    from backend.app.agents.rfp.sources import parse_upload, SourceError
    raw = office_zip({'[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'})
    with pytest.raises(SourceError, match='incomplete or corrupt'):
        parse_upload('incomplete.xlsx', raw)


def test_xlsx_declared_dimensions_are_bounded():
    from openpyxl import Workbook
    from backend.app.agents.rfp.sources import parse_upload, SourceError
    stream = BytesIO()
    workbook = Workbook()
    workbook.active.cell(10002, 1, 'Too many rows')
    workbook.save(stream)
    workbook.close()
    with pytest.raises(SourceError, match='10,000 rows'):
        parse_upload('oversized.xlsx', stream.getvalue())


@pytest.mark.parametrize('reported', [[], ['Verified criterion', 'Verified criterion'], ['Invented criterion']])
def test_alignment_rejects_missing_duplicate_or_invented_criteria(reported):
    from fastapi import HTTPException
    from backend.app.agents.curriculum.service import validated_alignment
    data = {'framework_name': 'Verified framework', 'overall_alignment_score': 90,
            'summary': 'Proposed coverage review', 'competency_alignment': [
                {'competency': c, 'status': 'fully_aligned', 'curriculum_coverage': 'Module 1',
                 'gaps': '', 'recommendation': ''} for c in reported],
            'missing_topics': [], 'strengths': [], 'recommendations': []}
    with pytest.raises(HTTPException) as error:
        validated_alignment(data, {'competencies': ['Verified criterion']})
    assert error.value.status_code == 503
