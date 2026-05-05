import { createContext, useContext } from "react";

// null как заглушка, чтобы TypeScript/линтеры не ругались
export const FormBuilderContext = createContext(null);

export function useFormBuilderContext() {
  const ctx = useContext(FormBuilderContext);
  if (!ctx) {
    throw new Error('useFormBuilderContext must be used within FormBuilderProvider');
  }
  return ctx;
}