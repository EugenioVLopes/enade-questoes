import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { PlaceholderSectionPage } from "@/components/layout/PlaceholderSectionPage";
import { RootIndexRedirect } from "@/components/layout/RootIndexRedirect";
import { TaxonomiaProvider } from "@/components/layout/TaxonomiaContext";
import { ProvasPage } from "@/features/provas/ProvasPage";

export const ROUTER_FUTURE_FLAGS: {
  readonly v7_relativeSplatPath: true;
  readonly v7_fetcherPersist: true;
  readonly v7_normalizeFormMethod: true;
  readonly v7_partialHydration: true;
  readonly v7_skipActionErrorRevalidation: true;
} = {
  v7_relativeSplatPath: true,
  v7_fetcherPersist: true,
  v7_normalizeFormMethod: true,
  v7_partialHydration: true,
  v7_skipActionErrorRevalidation: true,
};

export function createAppRoutes(): RouteObject[] {
  return [
    {
      path: "/",
      element: (
        <TaxonomiaProvider>
          <AppShell />
        </TaxonomiaProvider>
      ),
      children: [
        {
          index: true,
          element: <RootIndexRedirect />,
        },
        {
          path: "questoes",
          element: <PlaceholderSectionPage section="questoes" />,
        },
        {
          path: "revisao",
          element: <PlaceholderSectionPage section="revisao" />,
        },
        {
          path: "provas",
          element: <ProvasPage />,
        },
        {
          path: "taxonomias",
          element: <PlaceholderSectionPage section="taxonomias" />,
        },
        {
          path: "*",
          element: <RootIndexRedirect />,
        },
      ],
    },
  ];
}

export function createAppRouter(routes: RouteObject[] = createAppRoutes()) {
  return createBrowserRouter(routes, {
    future: ROUTER_FUTURE_FLAGS,
  });
}
