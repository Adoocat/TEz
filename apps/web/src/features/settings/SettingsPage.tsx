import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useParams } from "react-router";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { errorMessage } from "@/i18n";
import { ApiError } from "@/lib/api/query";

import {
  useDeleteSecret,
  useLibraryInfo,
  useSecrets,
  useSetSecret,
  useSettings,
  useUpdateSettings,
  type SecretName,
} from "./api";
import { BackupSection } from "./BackupSection";
import { settingsSections, type SettingsSection } from "./SettingsNav";

export function SettingsPage() {
  const { section } = useParams();
  const current = settingsSections.find((s) => s === section);
  if (!current) return <Navigate to="/settings/general" replace />;
  return <SettingsBody section={current} />;
}

function SettingsBody({ section }: { section: SettingsSection }) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-h1">{t(`settings.sections.${section}`)}</h1>
      {section === "general" && <GeneralSection />}
      {section === "sources" && <SourcesSection />}
      {section === "library" && <LibrarySection />}
      {section === "backup" && <BackupSection />}
      {section === "about" && <AboutSection />}
    </div>
  );
}

function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <section className="space-y-2 rounded-lg border border-line bg-raised p-4">
      <h2 className="text-h3">{label}</h2>
      {help && <p className="text-meta text-fg-muted">{help}</p>}
      {children}
    </section>
  );
}

function ErrorText({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  const detail =
    error instanceof ApiError
      ? { code: error.code, params: error.params }
      : { code: "network.unreachable" };
  return (
    <p role="alert" className="text-meta text-danger">
      {errorMessage(t, detail)}
    </p>
  );
}

function GeneralSection() {
  const { t } = useTranslation();
  const settings = useSettings();
  const update = useUpdateSettings();
  if (!settings.data) return <ErrorText error={settings.error} />;
  const { language, theme } = settings.data;

  return (
    <>
      <Field label={t("settings.language")} help={t("settings.languageHelp")}>
        <Segmented
          aria-label={t("settings.language")}
          value={language ?? "system"}
          options={(["system", "tr", "en"] as const).map((value) => ({
            value,
            label: t(`settings.languages.${value}`),
          }))}
          onValueChange={(value) => {
            update.mutate({ language: value === "system" ? null : value });
          }}
        />
      </Field>
      <Field label={t("settings.theme")}>
        <Segmented
          aria-label={t("settings.theme")}
          value={theme}
          options={(["system", "light", "dark"] as const).map((value) => ({
            value,
            label: t(`settings.themes.${value}`),
          }))}
          onValueChange={(value) => {
            update.mutate({ theme: value });
          }}
        />
      </Field>
      <ErrorText error={update.error} />
    </>
  );
}

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function SourcesSection() {
  const { t } = useTranslation();
  const settings = useSettings();
  if (!settings.data) return <ErrorText error={settings.error} />;
  return (
    <>
      <EmailField
        key={settings.data.sources_email ?? ""}
        initial={settings.data.sources_email ?? ""}
      />
      <Field label={t("settings.apiKeys")} help={t("settings.apiKeysHelp")}>
        <SecretList />
      </Field>
      <GrobidField key={settings.data.grobid_url ?? ""} initial={settings.data.grobid_url ?? ""} />
    </>
  );
}

// GROBID on this computer only (rule 1): the PDFs go to it.
const LOCAL_URL = /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?\/?$/;

function GrobidField({ initial }: { initial: string }) {
  const { t } = useTranslation();
  const update = useUpdateSettings();
  const [url, setUrl] = useState(initial);
  const trimmed = url.trim();
  const invalid = trimmed !== "" && !LOCAL_URL.test(trimmed);
  return (
    <Field label={t("settings.grobid")} help={t("settings.grobidHelp")}>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!invalid) update.mutate({ grobid_url: trimmed === "" ? null : trimmed });
        }}
      >
        <Input
          aria-label={t("settings.grobid")}
          aria-invalid={invalid}
          placeholder="http://localhost:8070"
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
          }}
        />
        <Button
          type="submit"
          variant="primary"
          disabled={invalid || trimmed === initial || update.isPending}
        >
          {t("settings.save")}
        </Button>
      </form>
      {invalid && <p className="text-meta text-danger">{t("settings.grobidInvalid")}</p>}
      <ErrorText error={update.error} />
    </Field>
  );
}

function EmailField({ initial }: { initial: string }) {
  const { t } = useTranslation();
  const update = useUpdateSettings();
  const [email, setEmail] = useState(initial);
  const trimmed = email.trim();
  const invalid = trimmed !== "" && !EMAIL.test(trimmed);

  return (
    <Field label={t("settings.email")} help={t("settings.emailHelp")}>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!invalid) update.mutate({ sources_email: trimmed === "" ? null : trimmed });
        }}
      >
        <Input
          type="email"
          aria-label={t("settings.email")}
          aria-invalid={invalid}
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
          }}
        />
        <Button
          type="submit"
          variant="primary"
          disabled={invalid || trimmed === initial || update.isPending}
        >
          {t("settings.save")}
        </Button>
      </form>
      {invalid && <p className="text-meta text-danger">{t("settings.emailInvalid")}</p>}
      <ErrorText error={update.error} />
    </Field>
  );
}

function SecretList() {
  const secrets = useSecrets();
  if (!secrets.data) return <ErrorText error={secrets.error} />;
  return (
    <ul className="divide-y divide-line">
      {secrets.data.map((secret) => (
        <SecretRow key={secret.name} name={secret.name} configured={secret.configured} />
      ))}
    </ul>
  );
}

function SecretRow({ name, configured }: { name: SecretName; configured: boolean }) {
  const { t } = useTranslation();
  const save = useSetSecret();
  const remove = useDeleteSecret();
  const [value, setValue] = useState("");
  const label = t(`settings.secretNames.${name}`);

  return (
    <li className="space-y-2 py-3">
      <div className="flex items-center justify-between">
        <span className="text-ui font-medium">{label}</span>
        <span className={configured ? "text-meta text-success" : "text-meta text-fg-muted"}>
          {configured ? t("settings.configured") : t("settings.notConfigured")}
        </span>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(
            { name, value },
            {
              onSuccess: () => {
                setValue("");
              },
            },
          );
        }}
      >
        <Input
          type="password"
          autoComplete="off"
          aria-label={label}
          placeholder={t("settings.keyPlaceholder")}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
          }}
        />
        <Button type="submit" variant="primary" disabled={value.trim() === "" || save.isPending}>
          {t("settings.save")}
        </Button>
        {configured && (
          <Button
            type="button"
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate(name);
            }}
          >
            {t("settings.remove")}
          </Button>
        )}
      </form>
      <ErrorText error={save.error ?? remove.error} />
    </li>
  );
}

function LibrarySection() {
  const { t } = useTranslation();
  const library = useLibraryInfo();
  if (!library.data) return <ErrorText error={library.error} />;
  return (
    <Field label={library.data.name}>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-ui">
        <dt className="text-fg-muted">{t("settings.libraryPath")}</dt>
        <dd className="break-all font-mono text-code">{library.data.path}</dd>
        <dt className="text-fg-muted">{t("settings.librarySchema")}</dt>
        <dd className="font-mono text-code">{library.data.schema_revision}</dd>
      </dl>
    </Field>
  );
}

function AboutSection() {
  const { t } = useTranslation();
  return (
    <Field label={t("app.name")}>
      <p className="text-ui">{t("settings.license")}</p>
      <p className="text-ui">{t("app.localFirst")}</p>
      <p className="font-mono text-code text-fg-muted">
        {t("settings.version")}: {__APP_VERSION__}
      </p>
    </Field>
  );
}
