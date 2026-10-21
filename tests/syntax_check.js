ObjC.import('Foundation');
const files = $.NSProcessInfo.processInfo.arguments;
const out = [];
for (let i = 4; i < files.count; i++) {
  const p = ObjC.unwrap(files.objectAtIndex(i));
  const src = ObjC.unwrap($.NSString.stringWithContentsOfFileEncodingError(p, $.NSUTF8StringEncoding, null));
  try { new Function(src); out.push('OK   ' + p); } catch (e) { out.push('FAIL ' + p + ': ' + e.message); }
}
out.join('\n');
