import { Building2, LayoutDashboard, type LucideIcon, Siren, Truck } from "lucide-react"

import type { Permission } from "@/features/auth/types"

export interface NavItem {
  to: string
  labelKey: "nav.commandCenter" | "nav.incidents" | "nav.resources" | "nav.organizations"
  icon: LucideIcon
  /** Permiso necesario para ver la entrada. Sin él, la opción no se muestra. */
  permission?: Permission
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", labelKey: "nav.commandCenter", icon: LayoutDashboard },
  { to: "/incidents", labelKey: "nav.incidents", icon: Siren, permission: "incidents:read" },
  { to: "/resources", labelKey: "nav.resources", icon: Truck, permission: "resources:read" },
  {
    to: "/organizations",
    labelKey: "nav.organizations",
    icon: Building2,
    permission: "organizations:read",
  },
]
