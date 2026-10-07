import csv
from django.http import StreamingHttpResponse


DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def safe_cell(value):
    if value is None:
        return ""
    text = str(value)
    stripped = text.lstrip()
    if stripped.startswith(DANGEROUS_PREFIXES):
        return "'" + text
    return text


class Echo:
    def write(self, value):
        return value


def streaming_csv(filename, headers, row_iterable):
    writer = csv.writer(Echo())
    stream = (writer.writerow([safe_cell(v) for v in row]) for row in ([headers], *row_iterable))
    response = StreamingHttpResponse(stream, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
