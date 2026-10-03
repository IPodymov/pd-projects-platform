import { createRouter, createWebHistory } from 'vue-router'
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/courses/:id', component: () => import('../views/CourseView.vue') },
    { path: '/account', component: () => import('../views/AccountView.vue') },
    { path: '/', component: () => import('../views/DashboardView.vue') },
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/invite', component: () => import('../views/InviteView.vue') },
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
