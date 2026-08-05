import {
  browserSupportsWebAuthn,
  startAuthentication,
  startRegistration
} from '@simplewebauthn/browser'

export const passkeyClientAvailable = () => (
  Boolean(window.isSecureContext) && browserSupportsWebAuthn()
)

export const getPasskeyUnavailableMessage = () => {
  if (!window.isSecureContext) {
    return 'Passkey需要通过HTTPS访问；本地开发可使用localhost。'
  }
  if (!browserSupportsWebAuthn()) {
    return '当前浏览器不支持Passkey，请升级浏览器或更换设备。'
  }
  return ''
}

export const runPasskeyAuthentication = async (optionsJSON) => (
  startAuthentication({ optionsJSON })
)

export const runPasskeyRegistration = async (optionsJSON) => (
  startRegistration({ optionsJSON })
)

export const friendlyPasskeyError = (error, fallback = 'Passkey操作失败，请重试。') => {
  const serverMessage = error?.response?.data?.error
  if (serverMessage) return serverMessage
  if (error?.name === 'NotAllowedError') return 'Passkey操作已取消或等待超时。'
  if (error?.name === 'InvalidStateError') return '当前设备中的这个Passkey已经绑定。'
  if (error?.name === 'NotSupportedError') return '当前设备不支持所需的Passkey验证方式。'
  if (error?.name === 'SecurityError') return '当前网站安全地址与Passkey配置不一致。'
  return fallback
}
