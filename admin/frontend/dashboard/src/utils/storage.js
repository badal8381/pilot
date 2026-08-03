export function siteStorageBytes(breakdown, siteName) {
  const files = breakdown?.bench?.sites?.find((site) => site.name === siteName)?.bytes || 0
  const database = (breakdown?.database?.databases || [])
    .filter((row) => row.site === siteName)
    .reduce((total, row) => total + row.bytes, 0)
  return files + database
}
