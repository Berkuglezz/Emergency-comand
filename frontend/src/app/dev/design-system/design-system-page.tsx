import { Info, Plus, RefreshCw, TriangleAlert } from "lucide-react"
import { type ReactNode, useState } from "react"
import { useTranslation } from "react-i18next"

import { ConfirmDialog } from "@/components/ops/confirm-dialog"
import { EtaText } from "@/components/ops/eta-text"
import { IncidentMarker } from "@/components/ops/incident-marker"
import { KpiTile } from "@/components/ops/kpi-tile"
import { Panel } from "@/components/ops/panel"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { ResourceMarker } from "@/components/ops/resource-marker"
import { StatusPill } from "@/components/ops/status-pill"
import { TONE_ICONS, TONE_STYLES, TONES } from "@/components/ops/tones"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

import {
  DATA_SAMPLES,
  KPI_SAMPLES,
  ETA_SAMPLE,
  ETA_SAMPLE_ASSIGNED_AT,
  MARKER_SAMPLES,
  RADII,
  SURFACE_TOKENS,
  TABLE_ROWS,
  TYPE_SCALE,
} from "./examples"

const BUTTON_VARIANTS = ["default", "secondary", "outline", "ghost", "destructive", "link"] as const
const BUTTON_SIZES = ["xs", "sm", "default", "lg"] as const

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 border-t pt-4">
      <h2 className="text-base font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Row({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2">{children}</div>
}

/**
 * Catálogo de desarrollo (/dev/design-system). Solo existe con
 * `import.meta.env.DEV`. Muestra los componentes reales de `components/ops` y
 * `components/ui` tal cual; sin lógica de negocio ni llamadas a la API.
 */
export function DesignSystemPage() {
  const { t } = useTranslation()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [destructiveOpen, setDestructiveOpen] = useState(false)
  const noop = () => undefined

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">{t("designSystem.title")}</h1>
        <p className="text-muted-foreground">{t("designSystem.description")}</p>
        <p className="text-xs text-muted-foreground">{t("designSystem.focusHint")}</p>
      </header>

      {/* --- Tokens ------------------------------------------------------ */}

      <Section title={t("designSystem.sections.surfaces")}>
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {SURFACE_TOKENS.map((token) => (
            <li key={token} className="flex flex-col gap-1">
              <div className="h-12 rounded-md border" style={{ background: `var(${token})` }} />
              <code className="font-data text-xs text-muted-foreground">{token}</code>
            </li>
          ))}
        </ul>
      </Section>

      <Section title={t("designSystem.sections.status")}>
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {TONES.map((tone) => {
            const styles = TONE_STYLES[tone]
            return (
              <li
                key={tone}
                className={cn(
                  "flex flex-col gap-1 rounded-md border p-3",
                  styles.border,
                  styles.subtle
                )}
              >
                <span className={cn("font-semibold", styles.text)}>
                  {t(`designSystem.status.${tone}`)}
                </span>
                <code className="font-data text-xs text-muted-foreground">
                  {t("designSystem.variants.text")}: {styles.text} ·{" "}
                  {t("designSystem.variants.subtle")}: {styles.subtle} ·{" "}
                  {t("designSystem.variants.border")}: {styles.border}
                </code>
              </li>
            )
          })}
        </ul>
      </Section>

      <Section title={t("designSystem.sections.icons")}>
        <ul className="flex flex-wrap gap-4">
          {TONES.map((tone) => {
            const Icon = TONE_ICONS[tone]
            return (
              <li key={tone} className={cn("flex items-center gap-1.5", TONE_STYLES[tone].text)}>
                <Icon aria-hidden className="size-4" />
                <span>{t(`designSystem.status.${tone}`)}</span>
              </li>
            )
          })}
        </ul>
      </Section>

      <Section title={t("designSystem.sections.typography")}>
        <ul className="flex flex-col gap-2">
          {TYPE_SCALE.map(({ className, label }) => (
            <li key={className} className="flex items-baseline gap-4">
              <code className="w-44 shrink-0 font-data text-xs text-muted-foreground">{label}</code>
              <span className={className}>{t("designSystem.typographySample")}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title={t("designSystem.sections.data")}>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
          <dt className="text-muted-foreground">{t("designSystem.dataLabels.code")}</dt>
          <dd className="font-data">{DATA_SAMPLES.code}</dd>
          <dt className="text-muted-foreground">{t("designSystem.dataLabels.time")}</dt>
          <dd className="font-data">{DATA_SAMPLES.time}</dd>
          <dt className="text-muted-foreground">{t("designSystem.dataLabels.coordinates")}</dt>
          <dd className="font-data">{DATA_SAMPLES.coordinates}</dd>
        </dl>
      </Section>

      <Section title={t("designSystem.sections.shape")}>
        <div className="flex flex-wrap items-center gap-4">
          {RADII.map(({ className, value }) => (
            <div
              key={className}
              className={cn(
                "flex size-20 items-center justify-center border bg-surface-1",
                className
              )}
            >
              <span className="text-xs text-muted-foreground">
                {t("designSystem.radiusLabel", { value })}
              </span>
            </div>
          ))}
          <div className="flex h-row items-center rounded-md border bg-surface-2 px-3">
            {t("designSystem.rowSample")}
          </div>
        </div>
      </Section>

      <Section title={t("designSystem.sections.motion")}>
        <StatusPill tone="critical" pulse>
          {t("designSystem.pulseSample")}
        </StatusPill>
      </Section>

      {/* --- components/ui ---------------------------------------------- */}

      <Section title={t("designSystem.sections.buttons")}>
        <Row>
          {BUTTON_VARIANTS.map((variant) => (
            <Button key={variant} variant={variant}>
              {t(`designSystem.buttons.variants.${variant}`)}
            </Button>
          ))}
        </Row>
        <span className="text-xs text-muted-foreground">{t("designSystem.buttons.sizes")}</span>
        <Row>
          {BUTTON_SIZES.map((size) => (
            <Button key={size} size={size} variant="outline">
              {size}
            </Button>
          ))}
          <Button size="icon" variant="outline" aria-label={t("designSystem.buttons.iconOnly")}>
            <RefreshCw />
          </Button>
        </Row>
        <span className="text-xs text-muted-foreground">{t("designSystem.buttons.states")}</span>
        <Row>
          <Button>
            <Plus data-icon="inline-start" aria-hidden />
            {t("designSystem.buttons.withIcon")}
          </Button>
          {BUTTON_VARIANTS.slice(0, 5).map((variant) => (
            <Button key={variant} variant={variant} disabled>
              {t("designSystem.buttons.disabled")}
            </Button>
          ))}
          <Button disabled aria-busy>
            {t("common.processing")}
          </Button>
        </Row>
      </Section>

      <Section title={t("designSystem.sections.fields")}>
        <FieldGroup className="max-w-sm">
          <Field>
            <FieldLabel htmlFor="ds-email">{t("designSystem.fields.emailLabel")}</FieldLabel>
            <Input
              id="ds-email"
              type="email"
              placeholder={t("designSystem.fields.emailPlaceholder")}
              aria-describedby="ds-email-description"
            />
            <FieldDescription id="ds-email-description">
              {t("designSystem.fields.emailDescription")}
            </FieldDescription>
          </Field>
          <Field data-disabled>
            <FieldLabel htmlFor="ds-disabled">{t("designSystem.fields.disabledLabel")}</FieldLabel>
            <Input id="ds-disabled" disabled defaultValue={DATA_SAMPLES.code} />
          </Field>
          <Field data-invalid>
            <FieldLabel htmlFor="ds-invalid">{t("designSystem.fields.invalidLabel")}</FieldLabel>
            <Input
              id="ds-invalid"
              type="password"
              aria-invalid
              aria-describedby="ds-invalid-error"
            />
            <FieldError id="ds-invalid-error">{t("designSystem.fields.invalidError")}</FieldError>
          </Field>
        </FieldGroup>
      </Section>

      <Section title={t("designSystem.sections.alerts")}>
        <div className="flex max-w-xl flex-col gap-2">
          <Alert>
            <Info aria-hidden />
            <AlertTitle>{t("designSystem.alerts.infoTitle")}</AlertTitle>
            <AlertDescription>{t("designSystem.alerts.infoDescription")}</AlertDescription>
          </Alert>
          <Alert variant="destructive">
            <TriangleAlert aria-hidden />
            <AlertTitle>{t("designSystem.alerts.errorTitle")}</AlertTitle>
            <AlertDescription>{t("designSystem.alerts.errorDescription")}</AlertDescription>
          </Alert>
        </div>
      </Section>

      <Section title={t("designSystem.sections.table")}>
        <div className="rounded-lg border bg-card">
          <Table>
            <TableCaption className="mb-2">{t("designSystem.table.caption")}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>{t("designSystem.table.code")}</TableHead>
                <TableHead>{t("designSystem.table.priority")}</TableHead>
                <TableHead>{t("designSystem.table.status")}</TableHead>
                <TableHead className="text-right">{t("designSystem.table.time")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {TABLE_ROWS.map((row) => (
                <TableRow key={row.code}>
                  <TableCell className="font-data">{row.code}</TableCell>
                  <TableCell>
                    <PriorityBadge priority={row.priority} />
                  </TableCell>
                  <TableCell>
                    <StatusPill tone={row.tone}>{t(`designSystem.status.${row.tone}`)}</StatusPill>
                  </TableCell>
                  <TableCell className="text-right font-data">{row.time}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Section>

      {/* --- components/ops --------------------------------------------- */}

      <Section title={t("designSystem.sections.priorityBadge")}>
        <Row>
          {PRIORITY_CODES.map((priority) => (
            <PriorityBadge key={priority} priority={priority} />
          ))}
          <PriorityBadge priority="critical" pulse />
        </Row>
      </Section>

      <Section title={t("designSystem.sections.incidentMarker")}>
        {/* Margen superior: el tooltip aparece encima al pasar el ratón o con el foco. */}
        <Row>
          <div className="flex flex-wrap items-center gap-3 pt-10">
            {MARKER_SAMPLES.map((sample) => (
              <IncidentMarker
                key={sample.code}
                code={sample.code}
                title={t("designSystem.markerTitle")}
                priority={sample.priority}
                status={sample.status}
                isSimulated
              />
            ))}
            <IncidentMarker
              code="INC-0040"
              title={t("designSystem.markerTitle")}
              priority="high"
              status="assessing"
              isSimulated={false}
              selected
            />
          </div>
        </Row>
      </Section>

      <Section title={t("designSystem.sections.resourceMarker")}>
        <Row>
          <ResourceMarker
            items={[
              {
                code: DATA_SAMPLES.resourceCode,
                typeLabel: t("resourceTypes.fire_engine"),
                etaLabel: t("ops.eta.short", {
                  minutes: ETA_SAMPLE.minutes,
                  distance: ETA_SAMPLE.distance_km,
                }),
              },
            ]}
          />
        </Row>
      </Section>

      <Section title={t("designSystem.sections.etaText")}>
        <div className="flex flex-col gap-2">
          <EtaText eta={ETA_SAMPLE} />
          <EtaText eta={ETA_SAMPLE} assignedAt={ETA_SAMPLE_ASSIGNED_AT} />
          <EtaText eta={null} unavailable="incident_without_coordinates" />
          <EtaText eta={null} unavailable="resource_without_position" />
        </div>
      </Section>

      <Section title={t("designSystem.sections.statusPill")}>
        <Row>
          {TONES.map((tone) => (
            <StatusPill key={tone} tone={tone}>
              {t(`designSystem.status.${tone}`)}
            </StatusPill>
          ))}
        </Row>
      </Section>

      <Section title={t("designSystem.sections.kpiTile")}>
        <div className="flex flex-wrap gap-2">
          <KpiTile label={t("designSystem.kpi.active")} value={KPI_SAMPLES.active} />
          <KpiTile
            label={t("designSystem.kpi.critical")}
            value={KPI_SAMPLES.critical}
            tone="critical"
          />
          <KpiTile
            label={t("designSystem.kpi.availability")}
            value={KPI_SAMPLES.availability}
            unit="%"
            tone="ok"
          />
          <KpiTile label={t("designSystem.kpi.noData")} value={null} />
          <KpiTile label={t("designSystem.kpi.loading")} state="loading" />
          <KpiTile label={t("designSystem.kpi.error")} state="error" />
        </div>
      </Section>

      <Section title={t("designSystem.sections.panel")}>
        <div className="grid gap-2 md:grid-cols-2">
          <Panel
            title={t("designSystem.panel.ready")}
            actions={
              <Button size="xs" variant="outline">
                {t("designSystem.panel.action")}
              </Button>
            }
          >
            <p>{t("designSystem.panel.content")}</p>
          </Panel>
          <Panel title={t("designSystem.panel.loading")} status="loading" />
          <Panel
            title={t("designSystem.panel.empty")}
            status="empty"
            empty={{ description: t("designSystem.panel.emptyDescription") }}
          />
          <Panel title={t("designSystem.panel.error")} status="error" error={{ onRetry: noop }} />
        </div>
      </Section>

      <Section title={t("designSystem.sections.dialog")}>
        <Row>
          <Dialog>
            <DialogTrigger render={<Button variant="outline" />}>
              {t("designSystem.dialog.open")}
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("designSystem.dialog.title")}</DialogTitle>
                <DialogDescription>{t("designSystem.dialog.description")}</DialogDescription>
              </DialogHeader>
            </DialogContent>
          </Dialog>
        </Row>
      </Section>

      <Section title={t("designSystem.sections.confirmDialog")}>
        <Row>
          <ConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            trigger={<Button variant="outline">{t("designSystem.confirm.openDefault")}</Button>}
            title={t("designSystem.confirm.defaultTitle")}
            description={t("designSystem.confirm.defaultDescription")}
            confirmLabel={t("designSystem.confirm.defaultConfirm")}
            onConfirm={() => {
              setConfirmOpen(false)
            }}
          />
          <ConfirmDialog
            open={destructiveOpen}
            onOpenChange={setDestructiveOpen}
            trigger={
              <Button variant="destructive">{t("designSystem.confirm.openDestructive")}</Button>
            }
            tone="destructive"
            title={t("designSystem.confirm.destructiveTitle")}
            description={t("designSystem.confirm.destructiveDescription")}
            confirmLabel={t("designSystem.confirm.destructiveConfirm")}
            onConfirm={() => {
              setDestructiveOpen(false)
            }}
          />
        </Row>
      </Section>
    </main>
  )
}
