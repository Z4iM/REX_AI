"""Bound Office ZIP containers before document libraries expand their XML."""
import zipfile

MAX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_MEMBERS = 2000


def validate_office_archive(source):
    try:
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS or sum(m.file_size for m in members) > MAX_EXPANDED_BYTES:
                raise ValueError("Office document exceeds the expanded content limit")
            if any(m.flag_bits & 1 for m in members):
                raise ValueError("Encrypted Office documents are not supported")
            if "[Content_Types].xml" not in archive.namelist():
                raise ValueError("File is not an Office document")
    except zipfile.BadZipFile:
        raise ValueError("Office document is corrupt") from None
