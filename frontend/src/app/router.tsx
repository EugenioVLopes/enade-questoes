import { createBrowserRouter } from "react-router-dom";

import { ShellPage } from "@/app/ShellPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <ShellPage />,
  },
]);
