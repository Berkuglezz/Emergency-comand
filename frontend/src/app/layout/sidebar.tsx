import { LogOut, PanelLeftClose, PanelLeftOpen } from "lucide-react"
import { useTranslation } from "react-i18next"
import { NavLink } from "react-router"

import { Button } from "@/components/ui/button"
import { hasPermission, useLogout, useSession } from "@/features/auth/hooks"
import { usePersistedToggle, viewportAtLeast } from "@/lib/use-persisted-toggle"
import { cn } from "@/lib/utils"

import { NAV_ITEMS } from "./nav-items"

/** Por debajo de este ancho la barra empieza plegada: el espacio es para el mapa. */
const EXPANDED_BY_DEFAULT_FROM = 1536

/**
 * Navegación principal. Se pliega a una columna de iconos; los nombres siguen
 * siendo accesibles (texto oculto) y aparecen como tooltip.
 */
export function Sidebar() {
  const { t } = useTranslation()
  const { data: user } = useSession()
  const logout = useLogout()
  const [expanded, setExpanded] = usePersistedToggle("sidebar", () =>
    viewportAtLeast(EXPANDED_BY_DEFAULT_FROM)
  )
  const items = NAV_ITEMS.filter((item) => !item.permission || hasPermission(user, item.permission))
  const ToggleIcon = expanded ? PanelLeftClose : PanelLeftOpen

  return (
    <aside
      data-expanded={expanded}
      className={cn(
        "flex shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground transition-[width] duration-150 ease-out motion-reduce:transition-none",
        expanded ? "w-52" : "w-12"
      )}
    >
      <nav aria-label={t("nav.label")} className="flex-1 p-2">
        <ul className="flex flex-col gap-0.5">
          {items.map(({ to, labelKey, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                title={expanded ? undefined : t(labelKey)}
                className={({ isActive }) =>
                  cn(
                    "flex h-row items-center gap-2 rounded-md px-2 text-muted-foreground outline-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
                    isActive && "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                  )
                }
              >
                <Icon aria-hidden className="size-4 shrink-0" />
                <span className={cn("truncate", !expanded && "sr-only")}>{t(labelKey)}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {user && (
        <div className="flex flex-col gap-2 border-t p-2">
          {expanded && (
            <div className="flex min-w-0 flex-col px-1">
              <span className="truncate font-medium">{user.full_name}</span>
              <span className="truncate text-xs text-muted-foreground">
                {t(`roles.${user.role}`)}
                {user.organization && ` · ${user.organization.name}`}
              </span>
            </div>
          )}
          <Button
            variant="outline"
            size={expanded ? "sm" : "icon-sm"}
            disabled={logout.isPending}
            title={
              expanded
                ? undefined
                : `${t("auth.logout")} · ${user.full_name} (${t(`roles.${user.role}`)})`
            }
            onClick={() => {
              logout.mutate()
            }}
          >
            <LogOut data-icon={expanded ? "inline-start" : undefined} aria-hidden />
            <span className={cn(!expanded && "sr-only")}>
              {logout.isPending ? t("auth.loggingOut") : t("auth.logout")}
            </span>
          </Button>
        </div>
      )}

      <div className="border-t p-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-expanded={expanded}
          aria-label={expanded ? t("layout.sidebar.collapse") : t("layout.sidebar.expand")}
          title={expanded ? t("layout.sidebar.collapse") : t("layout.sidebar.expand")}
          onClick={() => {
            setExpanded(!expanded)
          }}
        >
          <ToggleIcon aria-hidden />
        </Button>
      </div>
    </aside>
  )
}
