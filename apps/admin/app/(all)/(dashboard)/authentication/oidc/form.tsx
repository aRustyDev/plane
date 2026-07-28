/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * woven: OIDC SSO admin config form (Open-EE). Mirrors the CE Gitea form; edits the OIDC_*
 * InstanceConfiguration keys registered in plane-4cr. No IDP-sync toggle (OIDC sync isn't wired).
 */

import { useState } from "react";
import { isEmpty } from "lodash-es";
import Link from "next/link";
import { useForm } from "react-hook-form";
// plane internal packages
import { API_BASE_URL } from "@plane/constants";
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceOidcAuthenticationConfigurationKeys } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
import type { TCopyField } from "@/components/common/copy-field";
import { CopyField } from "@/components/common/copy-field";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type OidcConfigFormValues = Record<TInstanceOidcAuthenticationConfigurationKeys, string>;

export function InstanceOidcConfigForm(props: Props) {
  const { config } = props;
  // states
  const [isDiscardChangesModalOpen, setIsDiscardChangesModalOpen] = useState(false);
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<OidcConfigFormValues>({
    defaultValues: {
      OIDC_CLIENT_ID: config["OIDC_CLIENT_ID"],
      OIDC_CLIENT_SECRET: config["OIDC_CLIENT_SECRET"],
      OIDC_URL_AUTHORIZATION: config["OIDC_URL_AUTHORIZATION"],
      OIDC_URL_TOKEN: config["OIDC_URL_TOKEN"],
      OIDC_URL_USERINFO: config["OIDC_URL_USERINFO"],
      OIDC_URL_ENDPOINT: config["OIDC_URL_ENDPOINT"],
    },
  });

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";

  const OIDC_FORM_FIELDS: TControllerInputFormField[] = [
    {
      key: "OIDC_CLIENT_ID",
      type: "text",
      label: "Client ID",
      description: <>The client ID issued to Plane by your OpenID Connect provider.</>,
      placeholder: "plane-web",
      error: Boolean(errors.OIDC_CLIENT_ID),
      required: true,
    },
    {
      key: "OIDC_CLIENT_SECRET",
      type: "password",
      label: "Client secret",
      description: <>The client secret issued to Plane by your OpenID Connect provider.</>,
      placeholder: "•••••••••••••••••••••••••••••••••",
      error: Boolean(errors.OIDC_CLIENT_SECRET),
      required: true,
    },
    {
      key: "OIDC_URL_AUTHORIZATION",
      type: "text",
      label: "Authorization URL",
      description: (
        <>
          Your provider&apos;s <CodeBlock darkerShade>authorization_endpoint</CodeBlock>.
        </>
      ),
      placeholder: "https://id.example.com/oauth/v2/authorize",
      error: Boolean(errors.OIDC_URL_AUTHORIZATION),
      required: true,
    },
    {
      key: "OIDC_URL_TOKEN",
      type: "text",
      label: "Token URL",
      description: (
        <>
          Your provider&apos;s <CodeBlock darkerShade>token_endpoint</CodeBlock>.
        </>
      ),
      placeholder: "https://id.example.com/oauth/v2/token",
      error: Boolean(errors.OIDC_URL_TOKEN),
      required: true,
    },
    {
      key: "OIDC_URL_USERINFO",
      type: "text",
      label: "Userinfo URL",
      description: (
        <>
          Your provider&apos;s <CodeBlock darkerShade>userinfo_endpoint</CodeBlock>. It must return a verified{" "}
          <CodeBlock darkerShade>email</CodeBlock> claim.
        </>
      ),
      placeholder: "https://id.example.com/oidc/v1/userinfo",
      error: Boolean(errors.OIDC_URL_USERINFO),
      required: true,
    },
    {
      key: "OIDC_URL_ENDPOINT",
      type: "text",
      label: "Discovery URL (optional)",
      description: (
        <>
          Optional. Your provider&apos;s issuer or <CodeBlock darkerShade>.well-known/openid-configuration</CodeBlock>{" "}
          URL; used to derive the endpoints above when they are left blank.
        </>
      ),
      placeholder: "https://id.example.com/.well-known/openid-configuration",
      error: Boolean(errors.OIDC_URL_ENDPOINT),
      required: false,
    },
  ];

  const OIDC_SERVICE_FIELD: TCopyField[] = [
    {
      key: "Callback_URI",
      label: "Callback URI",
      url: `${originURL}/auth/oidc/callback/`,
      description: (
        <>
          We will auto-generate this. Register it as an <CodeBlock darkerShade>Authorized Redirect URI</CodeBlock> on
          your OpenID Connect provider.
        </>
      ),
    },
  ];

  const onSubmit = async (formData: OidcConfigFormValues) => {
    const payload: Partial<OidcConfigFormValues> = { ...formData };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Your OIDC authentication is configured. You should test it now.",
      });
      reset({
        OIDC_CLIENT_ID: response.find((item) => item.key === "OIDC_CLIENT_ID")?.value,
        OIDC_CLIENT_SECRET: response.find((item) => item.key === "OIDC_CLIENT_SECRET")?.value,
        OIDC_URL_AUTHORIZATION: response.find((item) => item.key === "OIDC_URL_AUTHORIZATION")?.value,
        OIDC_URL_TOKEN: response.find((item) => item.key === "OIDC_URL_TOKEN")?.value,
        OIDC_URL_USERINFO: response.find((item) => item.key === "OIDC_URL_USERINFO")?.value,
        OIDC_URL_ENDPOINT: response.find((item) => item.key === "OIDC_URL_ENDPOINT")?.value,
      });
    } catch (err) {
      console.error(err);
    }
  };

  const handleGoBack = (e: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => {
    if (isDirty) {
      e.preventDefault();
      setIsDiscardChangesModalOpen(true);
    }
  };

  return (
    <>
      <ConfirmDiscardModal
        isOpen={isDiscardChangesModalOpen}
        onDiscardHref="/authentication"
        handleClose={() => setIsDiscardChangesModalOpen(false)}
      />
      <div className="flex flex-col gap-8">
        <div className="grid w-full grid-cols-2 gap-x-12 gap-y-8">
          <div className="col-span-2 flex flex-col gap-y-4 pt-1 md:col-span-1">
            <div className="pt-2.5 text-18 font-medium">Provider-provided details for Plane</div>
            {OIDC_FORM_FIELDS.map((field) => (
              <ControllerInput
                key={field.key}
                control={control}
                type={field.type}
                name={field.key}
                label={field.label}
                description={field.description}
                placeholder={field.placeholder}
                error={field.error}
                required={field.required}
              />
            ))}
            <div className="flex flex-col gap-1 pt-4">
              <div className="flex items-center gap-4">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={(e) => void handleSubmit(onSubmit)(e)}
                  loading={isSubmitting}
                  disabled={!isDirty}
                >
                  {isSubmitting ? "Saving" : "Save changes"}
                </Button>
                <Link href="/authentication" className={getButtonStyling("secondary", "lg")} onClick={handleGoBack}>
                  Go back
                </Link>
              </div>
            </div>
          </div>
          <div className="col-span-2 md:col-span-1">
            <div className="flex flex-col gap-y-4 rounded-lg bg-layer-1 px-6 pt-1.5 pb-4">
              <div className="pt-2 text-18 font-medium">Plane-provided details for your provider</div>
              {OIDC_SERVICE_FIELD.map((field) => (
                <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
