import { createRouter, createWebHistory } from 'vue-router'
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/manage/institutions', component: () => import('../views/InstitutionsView.vue') },
    { path: '/manage/publications', component: () => import('../views/BlogView.vue') },
    { path: '/blog/new', component: () => import('../views/BlogEditorView.vue') },
    { path: '/blog/:id/edit', component: () => import('../views/BlogEditorView.vue') },
    {
      path: '/register',
      meta: { layout: 'auth' },
      component: () => import('../views/RegisterView.vue'),
    },
    { path: '/manage/users', component: () => import('../views/UsersView.vue') },
    { path: '/articles/:id', component: () => import('../views/ArticleView.vue') },
    { path: '/courses/:id', component: () => import('../views/CourseView.vue') },
    { path: '/account', component: () => import('../views/AccountView.vue') },
    { path: '/', component: () => import('../views/DashboardView.vue') },
    { path: '/login', meta: { layout: 'auth' }, component: () => import('../views/LoginView.vue') },
    {
      path: '/invite',
      meta: { layout: 'auth' },
      component: () => import('../views/InviteView.vue'),
    },
    { path: '/classes', component: () => import('../views/ClassesView.vue') },
    { path: '/projects/:id', component: () => import('../views/ProjectView.vue') },
    { path: '/schedule', component: () => import('../views/ScheduleView.vue') },
    { path: '/workshops', component: () => import('../views/WorkshopsView.vue') },
    {
      path: '/manage/:resource(publications|competitions)',
      component: () => import('../views/MaterialsView.vue'),
    },
    { path: '/manage/:resource', component: () => import('../views/ResourceView.vue') },
    { path: '/crm', component: () => import('../views/CrmView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
