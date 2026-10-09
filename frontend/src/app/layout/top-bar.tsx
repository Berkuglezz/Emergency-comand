import { CircleAlert, CircleCheck, CircleDashed, FlaskConical, Siren } from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { StatusPill } from "@/components/ops/status-pill"
import type { Tone } from "@/components/ops/tones"
import { type ConnectionState, useConnectionState } from "@/features/system/hooks"
import { DISPLAY_TIME_ZONE, formatShortDate, formatTime } from "@/lib/format"

const CONNECTION_TONE: Record<ConnectionState, Tone> = {
  online: "ok",
  degraded: "warning",
  offline: "inactive",
}

const CONNECTION_ICON = {
  online: CircleCheck,
  degraded: CircleAlert,
  offline: CircleDashed,
} as const

function Clock() {
  const { t } = useTranslation()
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(new Date())
    }, 1000)
    return () => {
      window.clearInterval(id)
    }
  }, [])

  return (
    <div className="flex items-baseline gap-2" title={DISPLAY_TIME_ZONE}>
      <span className="text-xs text-muted-foreground">{formatShortDate(now)}</span>
      {/* Sin aria-live: anunciar cada segundo saturaría al lector de pantalla. */}
      <time dateTime={now.toISOString()} className="font-data text-base font-medium">
        {formatTime(now)}
      </time>
      <span className="sr-only">{t("topBar.timeZone")}</span>
    </div>
  )
}

function ConnectionStatus() {
  const { t } = useTranslation()
  const { data: state = "offline", isPending } = useConnectionState()

  if (isPending) {
    return <StatusPill tone="inactive">{t("topBar.connection.checking")}</StatusPill>
  }
  return (
    <span role="status">
      <StatusPill tone={CONNECTION_TONE[state]} icon={CONNECTION_ICON[state]}>
        {t(`topBar.connection.${state}`)}
      </StatusPill>
    </span>
  )
}

/** Barra superior compacta: identidad, aviso de demo, conexión y reloj. */
export function TopBar() {
  const { t } = useTranslation()
  return (
    <header className="flex h-10 shrink-0 items-center justify-between gap-4 border-b bg-surface-1 px-3">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex shrink-0 items-center gap-2 font-semibold">
          <Siren aria-hidden className="size-4" />
          {t("app.name")}
        </span>
        <span
          className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground"
          title={t("app.demoNotice")}
        >
          <FlaskConical aria-hidden className="size-3.5 shrink-0" />
          <span className="truncate">{t("app.demoNotice")}</span>
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <ConnectionStatus />
        <Clock />
      </div>
    </header>
  )
}
