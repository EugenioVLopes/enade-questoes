import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { createAppRouter } from "@/app/router";

export interface AppProps {
  queryClient?: QueryClient;
  router?: ReturnType<typeof createAppRouter>;
}

function createDefaultQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
      },
    },
  });
}

export function App({ queryClient, router }: AppProps) {
  const [defaultQueryClient] = useState(() => queryClient ?? createDefaultQueryClient());
  const [defaultRouter] = useState(() => router ?? createAppRouter());

  const activeQueryClient = queryClient ?? defaultQueryClient;
  const activeRouter = router ?? defaultRouter;

  return (
    <QueryClientProvider client={activeQueryClient}>
      <RouterProvider router={activeRouter} future={{ v7_startTransition: true }} />
    </QueryClientProvider>
  );
}

export default App;
