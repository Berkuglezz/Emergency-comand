import { zodResolver } from "@hookform/resolvers/zod"
import type { TFunction } from "i18next"
import { NotebookPen } from "lucide-react"
import { useId, useMemo } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"

import { useAddIncidentNote } from "../hooks"
import { incidentErrorMessage } from "../presentation"

// Mismos límites que el backend (IncidentNoteCreate).
function createNoteSchema(t: TFunction) {
  return z.object({
    text: z
      .string()
      .trim()
      .min(1, { message: t("incidents.validation.noteRequired") })
      .max(2000, { message: t("incidents.validation.noteTooLong") }),
  })
}

type NoteSchema = ReturnType<typeof createNoteSchema>

/** Nota en el historial. Se admite también en incidentes cerrados o cancelados. */
export function NoteForm({ incidentId }: { incidentId: string }) {
  const { t } = useTranslation()
  const id = useId()
  const schema = useMemo(() => createNoteSchema(t), [t])
  const addNote = useAddIncidentNote(incidentId)
  const form = useForm<z.input<NoteSchema>, unknown, z.output<NoteSchema>>({
    resolver: zodResolver(schema),
    defaultValues: { text: "" },
  })
  const error = form.formState.errors.text
  const errorMessage =
    error?.message ?? (addNote.isError ? incidentErrorMessage(addNote.error, t) : null)

  const submit = form.handleSubmit((values) => {
    addNote.mutate(values, {
      onSuccess: () => {
        form.reset()
      },
    })
  })

  return (
    <form
      noValidate
      onSubmit={(event) => void submit(event)}
      className="flex flex-col gap-2 rounded-lg border bg-card p-3"
    >
      <Field data-invalid={errorMessage ? true : undefined}>
        <FieldLabel htmlFor={`${id}-note`}>{t("incidents.notes.label")}</FieldLabel>
        <Textarea
          id={`${id}-note`}
          rows={2}
          maxLength={2000}
          placeholder={t("incidents.notes.placeholder")}
          aria-invalid={errorMessage ? true : undefined}
          aria-describedby={errorMessage ? `${id}-note-error` : undefined}
          {...form.register("text")}
        />
        {errorMessage && <FieldError id={`${id}-note-error`}>{errorMessage}</FieldError>}
      </Field>
      <Button type="submit" variant="outline" className="self-end" disabled={addNote.isPending}>
        <NotebookPen data-icon="inline-start" aria-hidden />
        {addNote.isPending ? t("incidents.notes.submitting") : t("incidents.notes.submit")}
      </Button>
    </form>
  )
}
