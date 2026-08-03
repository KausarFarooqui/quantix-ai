import { create } from "zustand";

interface UiState {
  isCommandPaletteOpen: boolean;
  isSidebarCollapsed: boolean;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  toggleSidebar: () => void;
}

/**
 * Client-only UI state (command palette, sidebar collapse, etc.).
 * Server/remote data belongs in TanStack Query, never here — Zustand is
 * reserved for ephemeral, client-side interaction state.
 */
export const useUiStore = create<UiState>((set) => ({
  isCommandPaletteOpen: false,
  isSidebarCollapsed: false,
  openCommandPalette: () => set({ isCommandPaletteOpen: true }),
  closeCommandPalette: () => set({ isCommandPaletteOpen: false }),
  toggleSidebar: () =>
    set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
}));
