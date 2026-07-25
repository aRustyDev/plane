/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * woven: OIDC SSO row control on the authentication list (Open-EE). Mirrors gitea-config.tsx.
 */

import { observer } from "mobx-react";
import Link from "next/link";
// icons
import { Settings2 } from "lucide-react";
// plane internal packages
import { getButtonStyling } from "@plane/propel/button";
import type { TInstanceAuthenticationMethodKeys } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  disabled: boolean;
  updateConfig: (key: TInstanceAuthenticationMethodKeys, value: string) => void;
};

export const OidcConfiguration = observer(function OidcConfiguration(props: Props) {
  const { disabled, updateConfig } = props;
  // store
  const { formattedConfig } = useInstance();
  // derived values
  const OidcConfig = formattedConfig?.IS_OIDC_ENABLED ?? "";
  // usable once credentials plus either the explicit endpoints or a discovery URL are set
  const OidcConfigured =
    !!formattedConfig?.OIDC_CLIENT_ID &&
    !!formattedConfig?.OIDC_CLIENT_SECRET &&
    (!!formattedConfig?.OIDC_URL_AUTHORIZATION || !!formattedConfig?.OIDC_URL_ENDPOINT);

  return (
    <>
      {OidcConfigured ? (
        <div className="flex items-center gap-4">
          <Link href="/authentication/oidc" className={cn(getButtonStyling("link", "base"), "font-medium")}>
            Edit
          </Link>
          <ToggleSwitch
            value={Boolean(parseInt(OidcConfig))}
            onChange={() => {
              Boolean(parseInt(OidcConfig)) === true
                ? updateConfig("IS_OIDC_ENABLED", "0")
                : updateConfig("IS_OIDC_ENABLED", "1");
            }}
            size="sm"
            disabled={disabled}
          />
        </div>
      ) : (
        <Link href="/authentication/oidc" className={cn(getButtonStyling("secondary", "base"), "text-tertiary")}>
          <Settings2 className="h-4 w-4 p-0.5 text-tertiary" />
          Configure
        </Link>
      )}
    </>
  );
});
