import { create } from 'zustand';

interface AppState {
  isUploading: boolean;
  setIsUploading: (isUploading: boolean) => void;
  // Add other states here as needed
}

export const useStore = create<AppState>((set) => ({
  isUploading: false,
  setIsUploading: (isUploading) => set({ isUploading }),
}));
