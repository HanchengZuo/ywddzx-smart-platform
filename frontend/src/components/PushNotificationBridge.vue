<template>
  <aside v-if="show" class="push-permission-invite" role="status">
    <button class="dismiss" aria-label="暂不提醒" @click="dismiss">×</button
    ><strong>为这台设备开启系统通知</strong>
    <p>账号通知默认开启；浏览器授权需你确认。可在通知中心查看状态、开通指引并发送测试通知。</p>
    <button @click="open">前往通知中心</button>
  </aside>
</template>
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { pushCapability, syncDevice } from '../utils/webPush'
const props = defineProps({ userId: [String, Number] })
const router = useRouter(),
  show = ref(false)
let alive = true
const dismiss = () => {
  show.value = false
  localStorage.setItem(`push_invite_${props.userId}`, String(Date.now()))
}
const open = () => {
  dismiss()
  router.push('/notifications')
}
onMounted(async () => {
  try {
    const [{ data }] = await Promise.all([axios.get('/api/notifications/settings'), syncDevice()])
    if (!alive) return
    const recently =
      Number(localStorage.getItem(`push_invite_${props.userId}`) || 0) > Date.now() - 86400000
    show.value =
      data.enabled &&
      data.configured &&
      !recently &&
      pushCapability().code !== 'unsupported' &&
      window.Notification?.permission !== 'granted' &&
      router.currentRoute.value.path !== '/notifications'
  } catch {
    /* Notifications must never prevent normal application use. */
  }
})
onBeforeUnmount(() => {
  alive = false
})
</script>
<style scoped>
.push-permission-invite {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1900;
  width: min(360px, calc(100vw - 32px));
  box-sizing: border-box;
  background: #fff;
  color: #25475f;
  padding: 20px;
  border: 1px solid #b8d6e4;
  border-top: 3px solid #21899a;
  border-radius: 14px;
  box-shadow: 0 12px 40px #12334e25;
}
.push-permission-invite p {
  font-size: 13px;
  line-height: 1.7;
  color: #62788a;
}
.push-permission-invite button {
  border: 1px solid #bed2df;
  border-radius: 8px;
  background: #ecf5fa;
  color: #225b78;
  padding: 8px 12px;
  cursor: pointer;
}
.push-permission-invite .dismiss {
  position: absolute;
  right: 8px;
  top: 8px;
  border: 0;
  background: transparent;
  font-size: 20px;
  padding: 0 5px;
}
</style>
