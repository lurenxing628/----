"""Readable, reversible lists of business codes; legacy JSON stays in the codec."""

from core.errors import ValidationError

SEPARATORS = ",，、;；\r\n"
CLEAR_LIST_TOKEN = "清除"


def decode_code_list(value, field):
    if type(value) is not str:
        raise ValidationError("请填写工种编号，多个编号可用顿号分开，例如 OT1、OT2。", field=field)
    if value == CLEAR_LIST_TOKEN:
        return []
    codes, index = [], 0
    while True:
        code, index = _read_code(value, index, field)
        codes.append(code)
        if index == len(value):
            break
        separator = value[index]
        index += 1
        if separator == "\r" and index < len(value) and value[index] == "\n":
            index += 1
    if len(codes) != len(set(codes)):
        raise ValidationError("工种编号有重复，请每个编号只填一次。", field=field)
    return codes


def _read_code(value, start, field):
    """Read one unquoted code, or hand a quoted code to its dedicated reader."""
    index = start
    while index < len(value) and value[index] in " \t":
        index += 1
    if index < len(value) and value[index] == '"':
        return _read_quoted_code(value, index + 1, field)
    while index < len(value) and value[index] not in SEPARATORS:
        if value[index] == '"':
            raise _ambiguous(field)
        index += 1
    return _code(value[start:index], False, field), index


def _read_quoted_code(value, index, field):
    """Preserve quoted separators and line endings; a doubled quote is literal."""
    token = []
    while index < len(value):
        char = value[index]
        if char != '"':
            token.append(char)
            index += 1
            continue
        if index + 1 < len(value) and value[index + 1] == '"':
            token.append('"')
            index += 2
            continue
        index += 1
        while index < len(value) and value[index] in " \t":
            index += 1
        if index < len(value) and value[index] not in SEPARATORS:
            raise _ambiguous(field)
        return _code(token, True, field), index
    raise _ambiguous(field)


def _code(token, quoted, field):
    value = "".join(token)
    value = value if quoted else value.strip()
    if not value:
        raise ValidationError("编号列表中有空项，请删除多余的分隔符；移除全部工种请填清除。", field=field)
    return value


def _ambiguous(field):
    return ValidationError("编号列表的引号不配对或分隔不明确。编号本身含分隔符时用双引号括起，编号内的双引号写两次。", field=field)


def encode_code_list(values):
    if type(values) is not list or any(type(code) is not str or not code for code in values):
        raise ValueError("business code list must contain nonempty text")
    if not values:
        return CLEAR_LIST_TOKEN
    return "、".join('"' + code.replace('"', '""') + '"'
                    if code == CLEAR_LIST_TOKEN or code.startswith("[") or code != code.strip()
                    or any(char in code for char in SEPARATORS + '"') else code for code in values)
