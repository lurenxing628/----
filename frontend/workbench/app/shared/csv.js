function csvCell(value) {
  let text = String(value == null ? '' : value);
  if (/^[\s\uFEFF]*[=+@-]/.test(text)) text = "'" + text;
  return '"' + text.replace(/"/g, '""') + '"';
}

export { csvCell };
export default { csvCell };
