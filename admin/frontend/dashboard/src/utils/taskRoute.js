export function taskDetailRoute(taskId) {
  return { name: 'TaskDetail', params: { taskId } }
}

export function openTaskDetailPage(router, taskId) {
  router.push(taskDetailRoute(taskId))
}

export function siteDetailRoute(siteName, tab = 'apps') {
  return { name: 'SiteDetail', params: { name: siteName, tab } }
}

export function openSitePage(router, siteName) {
  router.push(siteDetailRoute(siteName))
}
