import { create } from "zustand";
import { persist } from "zustand/middleware";

export const COMPARE_FIELDS = ["Parties", "Charges", "Verdict", "Statutes", "Arguments", "Reasoning"] as const;
export type CompareField = (typeof COMPARE_FIELDS)[number];

const MAX_COMPARE = 3;

interface CompareState {
  selectedCaseIds: string[];
  visibleFields: CompareField[];
  limitReached: boolean;
  addCase: (id: string) => void;
  removeCase: (id: string) => void;
  clearAll: () => void;
  isSelected: (id: string) => boolean;
  toggleField: (field: CompareField) => void;
  dismissLimitReached: () => void;
}

export const useCompareStore = create<CompareState>()(
  persist(
    (set, get) => ({
      selectedCaseIds: [],
      visibleFields: [...COMPARE_FIELDS],
      limitReached: false,
      addCase: (id) =>
        set((state) => {
          if (state.selectedCaseIds.includes(id)) return state;
          if (state.selectedCaseIds.length >= MAX_COMPARE) {
            return { limitReached: true };
          }
          return { selectedCaseIds: [...state.selectedCaseIds, id], limitReached: false };
        }),
      removeCase: (id) =>
        set((state) => ({
          selectedCaseIds: state.selectedCaseIds.filter((caseId) => caseId !== id),
          limitReached: false,
        })),
      clearAll: () => set({ selectedCaseIds: [], limitReached: false }),
      isSelected: (id) => get().selectedCaseIds.includes(id),
      toggleField: (field) =>
        set((state) => ({
          visibleFields: state.visibleFields.includes(field)
            ? state.visibleFields.filter((f) => f !== field)
            : [...state.visibleFields, field],
        })),
      dismissLimitReached: () => set({ limitReached: false }),
    }),
    { name: "nyaya-compare" }
  )
);
