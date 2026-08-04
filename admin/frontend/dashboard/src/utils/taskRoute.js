export function taskDetailRoute(taskId) {
  return { name: 'TaskDetail', params: { taskId } }
}

export function openTaskDetailPage(router, taskId) {
  router.push(taskDetailRoute(taskId))
}

export function siteDetailRoute(siteName, tab = 'apps') {
  return { name: 'SiteDetail', params: { name: siteName, tab } }
}

export function openSitePage(router, siteName, app = '') {
  const route = siteDetailRoute(siteName)
  router.push(app ? { ...route, query: { app, action: 'install-app' } } : route)
}
