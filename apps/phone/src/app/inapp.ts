const KAKAOTALK = /KAKAOTALK/i
const OTHER_IN_APP = /NAVER\(inapp|Instagram|FBAN|FBAV|Line\/|DaumApps|everytimeApp/i

export function leaveInAppBrowser(): void {
  const ua = navigator.userAgent
  const { href, host, pathname, search } = window.location
  if (KAKAOTALK.test(ua)) {
    window.location.href = `kakaotalk://web/openExternal?url=${encodeURIComponent(href)}`
  } else if (OTHER_IN_APP.test(ua) && /Android/i.test(ua)) {
    window.location.href = `intent://${host}${pathname}${search}#Intent;scheme=https;package=com.android.chrome;end`
  }
}
