import { LogOut, Siren } from "lucide-react"
import { useTranslation } from "react-i18next"
import { NavLink } from "react-router"

import { Button } from "@/components/ui/button"
import { hasPermission, useLogout, useSession } from "@/features/auth/hooks"
import { cn } from "@/lib/utils"

import { NAV_ITEMS } from "./nav-items"

export function Sidebar() {
  const { t } = useTranslation()
  const { data: user } = useSession()
  const logout = useLogout()
  const items = NAV_ITEMS.filter((item) => !item.permission || hasPermission(user, item.permission))

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
      <div className="flex h-12 items-center gap-2 border-b px-3">
        <Siren aria-hidden className="size-4" />
        <span className="truncate text-sm font-semibold">{t("app.name")}</span>
      </div>

      <nav aria-label={t("nav.label")} className="flex-1 p-2">
        <ul className="flex flex-col gap-0.5">
          {items.map(({ to, labelKey, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex h-row items-center gap-2 rounded-md px-2 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                    isActive && "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                  )
                }
              >
                <Icon aria-hidden className="size-4" />
                {t(labelKey)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {user && (
        <div className="flex flex-col gap-2 border-t p-3">
          <div className="flex min-w-0 flex-col">
            <span className="truncate font-medium">{user.full_name}</span>
            <span className="truncate text-xs text-muted-foreground">
              {t(`roles.${user.role}`)}
              {user.organization && ` · ${user.organization.name}`}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={logout.isPending}
            onClick={() => {
              logout.mutate()
            }}
          >
            <LogOut data-icon="inline-start" aria-hidden />
            {logout.isPending ? t("auth.loggingOut") : t("auth.logout")}
          </Button>
        </div>
      )}
    </aside>
  )
}
