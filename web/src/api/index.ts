/** 后端接口封装（按模块分组）。 */
import service, { PageResult, pageParams } from '@/utils/request'

// ---------- 类型 ----------
export interface FieldDef {
  id?: number | null
  key: string
  label: string
  data_type: string
  required: boolean
  unique_value?: boolean
  options?: { label: string; value: string }[] | null
  default_value?: string | null
  placeholder?: string | null
  help_text?: string | null
  validation?: Record<string, unknown> | null
  show_in_list?: boolean
  searchable?: boolean
  sort_order?: number
}
export interface InfoModule {
  id: number
  code: string
  name: string
  geom_type: 'point' | 'line' | 'polygon'
  category?: string | null
  color: string
  icon?: string | null
  layer_order: number
  editable: boolean
  is_active: boolean
  description?: string | null
  fields: FieldDef[]
  feature_count?: number
  created_at?: string
  updated_at?: string
}
export interface ModuleBrief {
  id: number
  code: string
  name: string
  geom_type: 'point' | 'line' | 'polygon'
  geom_type_label?: string
  color: string
  layer_order: number
  field_count?: number
}
export interface FeatureItem {
  id: number
  module_id: number
  module_name?: string | null
  code: string | null
  name: string | null
  geometry: Record<string, unknown> | null
  properties: Record<string, unknown> | null
  declared_lng?: number | null
  declared_lat?: number | null
  center_lng?: number | null
  center_lat?: number | null
  area_m2?: number | null
  length_m?: number | null
  status: string
  remark?: string | null
  created_at?: string
  updated_at?: string
}
export interface BuildingItem {
  id: number
  code: string
  name: string
  address?: string | null
  parcel_code?: string | null
  region_code?: string | null
  geometry: Record<string, unknown> | null
  declared_lng?: number | null
  declared_lat?: number | null
  center_lng?: number | null
  center_lat?: number | null
  area_m2?: number | null
  floor_count?: number | null
  building_height?: number | null
  usage?: string | null
  structure_type?: string | null
  build_year?: number | null
  ownership?: string | null
  status: string
  remark?: string | null
  units: UnitBrief[]
  [key: string]: unknown
}
export interface BuildingMapItem {
  id: number
  code: string
  name: string
  status: string
  usage?: string | null
  geometry: Record<string, unknown> | null
}
export interface UnitBrief {
  relation_id: number
  unit_id: number
  name: string
  credit_code?: string | null
  relation_type: string
  share_ratio?: number | null
  is_primary: boolean
}
export interface UnitItem {
  id: number
  name: string
  credit_code?: string | null
  unit_type?: string | null
  legal_person?: string | null
  contact_name?: string | null
  phone?: string | null
  email?: string | null
  address?: string | null
  geometry?: Record<string, unknown> | null
  remark?: string | null
  building_count?: number | null
  buildings?: UnitBuilding[]
}
export interface UnitBuilding {
  relation_id: number
  building_id: number
  building_code: string
  building_name: string
  relation_type: string
  is_primary: boolean
  [key: string]: unknown
}
export interface CompareTask {
  id: number
  name: string
  source_type: 'feature' | 'building'
  module_id?: number | null
  module_name?: string | null
  threshold_m: number
  status: string
  total_count: number
  passed_count: number
  failed_count: number
  description?: string | null
  created_at?: string
  finished_at?: string | null
}
export interface CompareItem {
  id: number
  code?: string | null
  name?: string | null
  declared_lng?: number | null
  declared_lat?: number | null
  measured_lng?: number | null
  measured_lat?: number | null
  deviation_m?: number | null
  bearing_deg?: number | null
  bearing_text?: string | null
  threshold_m?: number | null
  passed?: boolean | null
  issue?: string | null
  issue_label?: string | null
  remark?: string | null
}
export interface RoleItem {
  id: number
  code: string
  name: string
  description?: string | null
  is_builtin: boolean
  permission_ids: number[]
  permission_codes: string[]
  user_count: number
}
export interface PermissionItem {
  id: number
  code: string
  name: string
  module: string
  action?: string | null
  perm_type: string
  sort_order: number
}
export interface ConfigItem {
  id: number
  key: string
  value: string | null
  label: string | null
  group: string
  value_type: string
  description?: string | null
}
export interface UserItem {
  id: number
  username: string
  real_name?: string | null
  phone?: string | null
  email?: string | null
  dept?: string | null
  is_active: boolean
  last_login_at?: string | null
  created_at?: string
  roles: string[]
  role_names?: string[]
  remark?: string | null
}
export interface LogItem {
  id: number
  username?: string | null
  action: string
  target?: string | null
  detail?: Record<string, unknown> | null
  ip?: string | null
  created_at?: string
}

// ---------- 工作台 ----------
export interface DashboardSummary {
  module_total: number
  feature_total: number
  building_total: number
  unit_total: number
  building_linked: number
  building_unlinked: number
  recent_tasks: {
    id: number
    name: string
    status: string
    total_count: number
    passed_count: number
    failed_count: number
    created_at: string
  }[]
  features_by_geom: { geom_type: string; count: number }[]
}

// ---------- 鉴权 ----------
export const authApi = {
  changePassword: (payload: { old_password: string; new_password: string }) =>
    service.post('/v1/change-password', payload),
}

// ---------- 信息模块 ----------
export const moduleApi = {
  list: (params: Record<string, unknown>) =>
    service.get('/v1/modules', { params }) as Promise<PageResult<InfoModule>>,
  brief: () => service.get('/v1/modules/brief') as Promise<ModuleBrief[]>,
  detail: (id: number) => service.get(`/v1/modules/${id}`) as Promise<InfoModule>,
  create: (payload: Partial<InfoModule>) => service.post('/v1/modules', payload) as Promise<InfoModule>,
  update: (id: number, payload: Partial<InfoModule>) =>
    service.put(`/v1/modules/${id}`, payload) as Promise<InfoModule>,
  remove: (id: number) => service.delete(`/v1/modules/${id}`),
}

// ---------- 采集要素 ----------
export interface FeatureMapGroup {
  module_id: number
  module_name: string | null
  geom_type: string
  color: string
  features: Array<{
    id: number
    module_id: number
    code: string | null
    name: string | null
    geometry: Record<string, unknown>
    properties: Record<string, unknown>
  }>
}
export const featureApi = {
  list: (params: Record<string, unknown>) =>
    service.get('/v1/features', { params }) as Promise<PageResult<FeatureItem>>,
  detail: (id: number) => service.get(`/v1/features/${id}`) as Promise<FeatureItem>,
  create: (payload: Record<string, unknown>) => service.post('/v1/features', payload) as Promise<FeatureItem>,
  update: (id: number, payload: Record<string, unknown>) =>
    service.put(`/v1/features/${id}`, payload) as Promise<FeatureItem>,
  remove: (id: number) => service.delete(`/v1/features/${id}`),
  batchRemove: (ids: number[]) => service.post('/v1/features/batch-delete', { ids }),
  map: (moduleIds: number[], limit = 5000) =>
    service.get('/v1/features/map', {
      params: { module_ids: moduleIds.join(','), limit },
    }) as Promise<FeatureMapGroup[]>,
  stats: () => service.get('/v1/features/stats'),
  blank: (moduleId: number) =>
    service.get(`/v1/features/template/${moduleId}`) as Promise<{
      properties: Record<string, unknown>
      geom_type: string
      module: string
    }>,
}

// ---------- 建筑物 ----------
export const buildingApi = {
  list: (params: Record<string, unknown>) =>
    service.get('/v1/buildings', { params }) as Promise<PageResult<BuildingItem>>,
  detail: (id: number) => service.get(`/v1/buildings/${id}`) as Promise<BuildingItem>,
  create: (payload: Record<string, unknown>) => service.post('/v1/buildings', payload) as Promise<BuildingItem>,
  update: (id: number, payload: Record<string, unknown>) =>
    service.put(`/v1/buildings/${id}`, payload) as Promise<BuildingItem>,
  remove: (id: number) => service.delete(`/v1/buildings/${id}`),
  map: (limit = 5000) => service.get('/v1/buildings/map', { params: { limit } }),
  summary: () => service.get('/v1/buildings/summary'),
  attachUnit: (buildingId: number, payload: Record<string, unknown>) =>
    service.post(`/v1/buildings/${buildingId}/units`, payload),
  updateRelation: (buildingId: number, relationId: number, payload: Record<string, unknown>) =>
    service.put(`/v1/buildings/${buildingId}/units/${relationId}`, payload),
  detachUnit: (buildingId: number, relationId: number) =>
    service.delete(`/v1/buildings/${buildingId}/units/${relationId}`),
}

// ---------- 建筑物外景 ----------
export interface FacadeBuildingBrief {
  id: number
  code: string
  name: string
  address?: string | null
}
export interface FacadeItem {
  id: number
  building_id: number
  kind: string
  facade: string
  facade_label?: string
  kind_label?: string
  floor_no?: number | null
  file_name: string
  file_path: string
  thumb_path?: string | null
  mime?: string | null
  file_size: number
  width?: number | null
  height?: number | null
  taken_at?: string | null
  lng?: number | null
  lat?: number | null
  uploader_name?: string | null
  remark?: string | null
  is_primary: boolean
  created_at?: string
  url?: string | null
  thumb_url?: string | null
}
export interface FacadeStats {
  total: number
  by_facade: Record<string, number>
  by_kind: Record<string, number>
  cover_url?: string | null
}
export const facadeApi = {
  buildings: (keyword?: string) =>
    service.get('/v1/facade/buildings', {
      params: keyword ? { keyword } : {},
    }) as Promise<FacadeBuildingBrief[]>,
  list: (params: Record<string, unknown>) =>
    service.get('/v1/facade', { params }) as Promise<PageResult<FacadeItem>>,
  stats: (buildingId?: number) =>
    service.get('/v1/facade/stats', {
      params: buildingId ? { building_id: buildingId } : {},
    }) as Promise<FacadeStats>,
  upload: (
    payload: {
      building_id: number
      kind: string
      facade: string
      floor_no?: number | null
      taken_at?: string | null
      remark?: string | null
      files: File[]
    },
    onProgress?: (percent: number) => void,
  ) => {
    const form = new FormData()
    form.append('building_id', String(payload.building_id))
    form.append('kind', payload.kind)
    form.append('facade', payload.facade)
    if (payload.floor_no !== null && payload.floor_no !== undefined) {
      form.append('floor_no', String(payload.floor_no))
    }
    if (payload.taken_at) form.append('taken_at', payload.taken_at)
    if (payload.remark) form.append('remark', payload.remark)
    for (const file of payload.files) form.append('files', file, file.name)
    return service.post('/v1/facade/upload', form, {
      // 大尺寸全景图上传较慢，放宽超时
      timeout: 300000,
      onUploadProgress: (e: { loaded: number; total?: number }) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    }) as Promise<FacadeItem[]>
  },
  update: (id: number, payload: Record<string, unknown>) =>
    service.put(`/v1/facade/${id}`, payload) as Promise<FacadeItem>,
  remove: (id: number) => service.delete(`/v1/facade/${id}`),
  batchRemove: (ids: number[]) => service.post('/v1/facade/batch-delete', { ids }),
  /** 后端返回的是 /api/uploads/... 相对地址，需要拼上部署前缀 */
  fileUrl: (url?: string | null) => (url ? `${window._config?.BASE_API || ''}${url}` : ''),
}

// ---------- 单位 ----------
export const unitApi = {
  list: (params: Record<string, unknown>) =>
    service.get('/v1/units', { params }) as Promise<PageResult<UnitItem>>,
  detail: (id: number) => service.get(`/v1/units/${id}`) as Promise<UnitItem>,
  create: (payload: Record<string, unknown>) => service.post('/v1/units', payload) as Promise<UnitItem>,
  update: (id: number, payload: Record<string, unknown>) =>
    service.put(`/v1/units/${id}`, payload) as Promise<UnitItem>,
  remove: (id: number) => service.delete(`/v1/units/${id}`),
  positions: (limit = 5000) => service.get('/v1/units/positions', { params: { limit } }),
  types: () =>
    service.get('/v1/units/types') as Promise<{ value: string; count: number }[]>,
  buildings: (id: number) => service.get(`/v1/units/${id}/buildings`) as Promise<UnitBuilding[]>,
}

// ---------- 比对 ----------
export const compareApi = {
  tasks: (params: Record<string, unknown>) =>
    service.get('/v1/compare/tasks', { params }) as Promise<PageResult<CompareTask>>,
  taskDetail: (id: number, issue?: string) =>
    service.get(`/v1/compare/tasks/${id}`, { params: issue ? { issue } : {} }) as Promise<
      CompareTask & { items: CompareItem[] }
    >,
  run: (payload: Record<string, unknown>) =>
    service.post('/v1/compare/tasks', payload) as Promise<CompareTask & { summary: Record<string, number> }>,
  rerun: (id: number) => service.post(`/v1/compare/tasks/${id}/rerun`),
  remove: (id: number) => service.delete(`/v1/compare/tasks/${id}`),
  updateItem: (itemId: number, remark: string | null) =>
    service.put(`/v1/compare/items/${itemId}`, { remark }),
  map: (id: number) =>
    service.get(`/v1/compare/tasks/${id}/map`) as Promise<{
      points: CompareMapShape[]
      lines: CompareMapShape[]
    }>,
  exportUrl: (id: number) => `/api/v1/compare/tasks/${id}/export.csv`,
  exportBlob: (id: number) =>
    service.get(`/v1/compare/tasks/${id}/export.csv`, { responseType: 'blob' }) as Promise<Blob>,
}
export interface CompareMapShape {
  id: string
  pair_id: number
  kind?: string
  label: string
  color: string
  geometry: Record<string, unknown>
}

// ---------- 系统设置 ----------
export const systemApi = {
  users: (params: Record<string, unknown>) =>
    service.get('/v1/users', { params }) as Promise<PageResult<UserItem>>,
  createUser: (payload: Record<string, unknown>) => service.post('/v1/users', payload),
  updateUser: (id: number, payload: Record<string, unknown>) => service.put(`/v1/users/${id}`, payload),
  removeUser: (id: number) => service.delete(`/v1/users/${id}`),
  resetPassword: (id: number, newPassword: string) =>
    service.post(`/v1/users/${id}/reset-password`, null, { params: { new_password: newPassword } }),
  roles: () => service.get('/v1/roles') as Promise<RoleItem[]>,
  createRole: (payload: Record<string, unknown>) => service.post('/v1/roles', payload) as Promise<RoleItem>,
  updateRole: (id: number, payload: Record<string, unknown>) =>
    service.put(`/v1/roles/${id}`, payload) as Promise<RoleItem>,
  setRolePermissions: (id: number, permissionIds: number[]) =>
    service.put(`/v1/roles/${id}/permissions`, { permission_ids: permissionIds }) as Promise<RoleItem>,
  removeRole: (id: number) => service.delete(`/v1/roles/${id}`),
  permissions: (permType?: string) =>
    service.get('/v1/permissions', { params: permType ? { perm_type: permType } : {} }) as Promise<PermissionItem[]>,
  configs: (group?: string) =>
    service.get('/v1/configs', { params: group ? { group } : {} }) as Promise<ConfigItem[]>,
  saveConfigs: (items: Partial<ConfigItem>[]) => service.put('/v1/configs', items),
  removeConfig: (id: number) => service.delete(`/v1/configs/${id}`),
  logs: (params: Record<string, unknown>) =>
    service.get('/v1/logs', { params }) as Promise<PageResult<LogItem>>,
}

// ---------- 工作台 ----------
export const dashboardApi = {
  summary: () => service.get<DashboardSummary>('/v1/dashboard/summary'),
}

export { pageParams }
