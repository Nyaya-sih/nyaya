import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UiState {
  theme: "light" | "dark";
  sidebarOpen: boolean;
  filterPanelOpen: boolean;
  toggleTheme: () => void;
  setSidebarOpen: (open: boolean) => void;
  setFilterPanelOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: "light",
      sidebarOpen: false,
      filterPanelOpen: true,
      toggleTheme: () =>
        set((state) => ({ theme: state.theme === "light" ? "dark" : "light" })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setFilterPanelOpen: (open) => set({ filterPanelOpen: open }),
    }),
    { name: "nyaya-ui" }
  )
);
