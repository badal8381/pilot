export const taskDetailRoute = (taskId) => {
  return { name: 'TaskDetail', params: { taskId } }
}

export const openTaskDetailPage = (router, taskId) => {
  router.push(taskDetailRoute(taskId))
}

export const siteDetailRoute = (siteName, tab = 'apps') => {
  return { name: 'SiteDetail', params: { name: siteName, tab } }
}

export const openSitePage = (router, siteName, app = '') => {
  const route = siteDetailRoute(siteName)
  router.push(app ? { ...route, query: { app, action: 'install-app' } } : route)
}
