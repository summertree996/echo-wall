import { createRouter, createWebHistory } from 'vue-router'

const LandingView = () => import('./views/LandingView.vue')
const EnterView = () => import('./views/EnterView.vue')
const ProfileView = () => import('./views/ProfileView.vue')
const AdminWallsView = () => import('./views/AdminWallsView.vue')
const ResearchDashboardView = () => import('./views/ResearchDashboardView.vue')
const WechatAssistantView = () => import('./views/WechatAssistantView.vue')
const WallView = () => import('./views/WallView.vue')

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingView },
    { path: '/enter', name: 'enter', component: EnterView },
    { path: '/me', name: 'me', component: ProfileView },
    { path: '/admin', redirect: '/admin/walls' },
    { path: '/admin/walls', name: 'admin-walls', component: AdminWallsView },
    { path: '/admin/walls/:wallId/research', name: 'research-dashboard', component: ResearchDashboardView },
    { path: '/admin/wechat-assistant', name: 'wechat-assistant', component: WechatAssistantView },
    { path: '/wall/:wallId', name: 'wall', component: WallView },
  ],
})
