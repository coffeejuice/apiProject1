import { create } from 'zustand'
import { apiClient } from '../lib/apiClient'
import type {
  DieAssemblyRecord,
  DieRecord,
  DieTypeRecord,
  LibraryDbUserRecord,
  MaterialClassificationCatalogRecord,
  MaterialRecord,
  PressModeRecord,
  PressRecord,
} from '../types/api'

interface LibraryState {
  users: LibraryDbUserRecord[]
  dieTypes: DieTypeRecord[]
  materials: MaterialRecord[]
  materialClassificationCatalog: MaterialClassificationCatalogRecord | null
  dies: DieRecord[]
  dieAssemblies: DieAssemblyRecord[]
  presses: PressRecord[]
  pressModes: PressModeRecord[]
  isLoading: boolean
  hasLoaded: boolean
  error: string | null

  fetchAll: () => Promise<void>
}

export const useLibraryStore = create<LibraryState>((set) => ({
  users: [],
  dieTypes: [],
  materials: [],
  materialClassificationCatalog: null,
  dies: [],
  dieAssemblies: [],
  presses: [],
  pressModes: [],
  isLoading: false,
  hasLoaded: false,
  error: null,

  fetchAll: async () => {
    set({ isLoading: true, error: null })

    const [
      usersResponse,
      dieTypesResponse,
      materialsResponse,
      materialClassificationResponse,
      diesResponse,
      dieAssembliesResponse,
      pressesResponse,
      pressModesResponse,
    ] = await Promise.all([
      apiClient.get<LibraryDbUserRecord[]>('/library/db/users'),
      apiClient.get<DieTypeRecord[]>('/library/db/die-types'),
      apiClient.get<MaterialRecord[]>('/library/db/materials'),
      apiClient.get<MaterialClassificationCatalogRecord>('/library/db/material-classification'),
      apiClient.get<DieRecord[]>('/library/db/dies'),
      apiClient.get<DieAssemblyRecord[]>('/library/db/die-assemblies'),
      apiClient.get<PressRecord[]>('/library/db/presses'),
      apiClient.get<PressModeRecord[]>('/library/db/press-modes'),
    ])

    const failedResponse = [
      usersResponse,
      dieTypesResponse,
      materialsResponse,
      materialClassificationResponse,
      diesResponse,
      dieAssembliesResponse,
      pressesResponse,
      pressModesResponse,
    ].find((response) => !response.ok)

    set({
      users: usersResponse.ok && usersResponse.data ? usersResponse.data : [],
      dieTypes: dieTypesResponse.ok && dieTypesResponse.data ? dieTypesResponse.data : [],
      materials: materialsResponse.ok && materialsResponse.data ? materialsResponse.data : [],
      materialClassificationCatalog:
        materialClassificationResponse.ok && materialClassificationResponse.data
          ? materialClassificationResponse.data
          : null,
      dies: diesResponse.ok && diesResponse.data ? diesResponse.data : [],
      dieAssemblies: dieAssembliesResponse.ok && dieAssembliesResponse.data ? dieAssembliesResponse.data : [],
      presses: pressesResponse.ok && pressesResponse.data ? pressesResponse.data : [],
      pressModes: pressModesResponse.ok && pressModesResponse.data ? pressModesResponse.data : [],
      isLoading: false,
      hasLoaded: true,
      error: failedResponse?.errorMessage || null,
    })
  },
}))
