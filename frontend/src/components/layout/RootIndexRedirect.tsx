import { Navigate, useLocation } from "react-router-dom";

export function RootIndexRedirect() {
  const { search } = useLocation();
  return <Navigate to={{ pathname: "/provas", search }} replace />;
}
