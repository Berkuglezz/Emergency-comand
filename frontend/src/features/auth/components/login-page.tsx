import { zodResolver } from "@hookform/resolvers/zod"
import type { TFunction } from "i18next"
import { LogIn, Siren, TriangleAlert } from "lucide-react"
import { useMemo } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { Navigate, useLocation, useNavigate } from "react-router"
import { z } from "zod"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ApiError } from "@/lib/api-client"

import { useLogin, useSession } from "../hooks"

// Mismos límites que valida el backend (schemas/auth.py).
function createLoginSchema(t: TFunction) {
  return z.object({
    email: z
      .string()
      .trim()
      .min(1, { message: t("auth.validation.emailRequired") })
      .max(254, { message: t("auth.validation.emailInvalid") })
      .pipe(z.email({ message: t("auth.validation.emailInvalid") })),
    password: z
      .string()
      .min(1, { message: t("auth.validation.passwordRequired") })
      .max(256, { message: t("auth.validation.passwordTooLong") }),
  })
}

type LoginSchema = ReturnType<typeof createLoginSchema>

function loginErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_credentials") return t("auth.errors.invalidCredentials")
    if (error.isNetworkError) return t("auth.errors.network")
  }
  return t("auth.errors.unexpected")
}

function redirectTarget(state: unknown): string {
  if (typeof state === "object" && state !== null && "from" in state) {
    const { from } = state
    // Solo rutas internas: nunca redirigir a otra URL.
    if (typeof from === "string" && from.startsWith("/") && !from.startsWith("//")) return from
  }
  return "/"
}

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const session = useSession()
  const login = useLogin()
  const schema = useMemo(() => createLoginSchema(t), [t])
  const target = redirectTarget(location.state)

  const form = useForm<z.input<LoginSchema>, unknown, z.output<LoginSchema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  })
  const { errors } = form.formState

  if (session.data) return <Navigate to={target} replace />

  const onSubmit = form.handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => {
        void navigate(target, { replace: true })
      },
      onError: () => {
        // La contraseña nunca se conserva tras un intento fallido.
        form.resetField("password")
      },
    })
  })

  return (
    <main className="flex min-h-dvh items-center justify-center p-6">
      <div className="flex w-full max-w-sm flex-col gap-6 rounded-lg border bg-card p-6">
        <header className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Siren aria-hidden className="size-5" />
            <h1 className="text-lg font-semibold">{t("app.name")}</h1>
          </div>
          <p className="text-muted-foreground">{t("auth.login.subtitle")}</p>
        </header>

        {login.isError && (
          <Alert variant="destructive">
            <TriangleAlert aria-hidden />
            <AlertTitle>{t("auth.login.failed")}</AlertTitle>
            <AlertDescription>{loginErrorMessage(login.error, t)}</AlertDescription>
          </Alert>
        )}

        <form noValidate onSubmit={(event) => void onSubmit(event)}>
          <FieldGroup>
            <Field data-invalid={errors.email ? true : undefined}>
              <FieldLabel htmlFor="login-email">{t("auth.login.email")}</FieldLabel>
              <Input
                id="login-email"
                type="email"
                autoComplete="username"
                autoFocus
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? "login-email-error" : undefined}
                {...form.register("email")}
              />
              {errors.email?.message && (
                <FieldError id="login-email-error">{errors.email.message}</FieldError>
              )}
            </Field>
            <Field data-invalid={errors.password ? true : undefined}>
              <FieldLabel htmlFor="login-password">{t("auth.login.password")}</FieldLabel>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                aria-invalid={errors.password ? true : undefined}
                aria-describedby={errors.password ? "login-password-error" : undefined}
                {...form.register("password")}
              />
              {errors.password?.message && (
                <FieldError id="login-password-error">{errors.password.message}</FieldError>
              )}
            </Field>
            <Button type="submit" disabled={login.isPending} aria-busy={login.isPending}>
              <LogIn data-icon="inline-start" aria-hidden />
              {login.isPending ? t("auth.login.submitting") : t("auth.login.submit")}
            </Button>
          </FieldGroup>
        </form>

        <p className="text-xs text-muted-foreground">{t("app.demoNotice")}</p>
      </div>
    </main>
  )
}
