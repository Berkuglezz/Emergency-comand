import { TriangleAlert } from "lucide-react"
import { type ReactElement, type ReactNode, useRef } from "react"
import { useTranslation } from "react-i18next"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

interface ConfirmDialogProps {
  title: string
  description: string
  confirmLabel: string
  cancelLabel?: string
  /** `destructive`: acción peligrosa o irreversible (CLAUDE.md §6). */
  tone?: "default" | "destructive"
  /** Acción en curso: los botones se deshabilitan y no se puede cerrar. */
  pending?: boolean
  onConfirm: () => void
  /** Elemento que abre el diálogo (normalmente un Button). */
  trigger?: ReactElement
  /**
   * Controlado: confirmar no cierra el diálogo por sí solo. Quien lo usa lo
   * cierra cuando la acción termina (o lo mantiene abierto si falla).
   */
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Contenido adicional entre la descripción y los botones (p. ej. un motivo opcional). */
  children?: ReactNode
}

/**
 * Confirmación explícita de una acción. El foco inicial va a «Cancelar», para
 * que pulsar Intro por inercia nunca confirme una acción peligrosa.
 */
export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  cancelLabel,
  tone = "default",
  pending = false,
  onConfirm,
  trigger,
  open,
  onOpenChange,
  children,
}: ConfirmDialogProps) {
  const { t } = useTranslation()
  const cancelRef = useRef<HTMLButtonElement>(null)
  const destructive = tone === "destructive"

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (pending && !next) return
        onOpenChange(next)
      }}
    >
      {trigger && <AlertDialogTrigger render={trigger} />}
      <AlertDialogContent initialFocus={cancelRef} aria-busy={pending}>
        <AlertDialogHeader>
          {destructive && (
            <AlertDialogMedia className="bg-critical-subtle text-critical">
              <TriangleAlert aria-hidden />
            </AlertDialogMedia>
          )}
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {children}
        <AlertDialogFooter>
          <AlertDialogCancel ref={cancelRef} disabled={pending}>
            {cancelLabel ?? t("common.cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            variant={destructive ? "destructive" : "default"}
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? t("common.processing") : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
