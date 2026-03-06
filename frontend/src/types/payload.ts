/**
 * Payload Library TypeScript Definitions
 *
 * Type definitions for the AgentTwister payload library API.
 * These types ensure type safety when working with payload templates
 * in the frontend application.
 */

/**
 * OWASP LLM Top-10 Attack Categories
 */
export enum AttackCategory {
  LLM01_PROMPT_INJECTION = "LLM01: Prompt Injection",
  LLM02_INSECURE_OUTPUT = "LLM02: Insecure Output Handling",
  LLM03_DATA_POISONING = "LLM03: Training Data Poisoning",
  LLM04_MODEL_DOS = "LLM04: Model Denial of Service",
  LLM05_SUPPLY_CHAIN = "LLM05: Supply Chain Vulnerabilities",
  LLM06_SENSITIVE_INFO = "LLM06: Sensitive Information Disclosure",
  LLM07_INSECURE_PLUGIN = "LLM07: Insecure Plugin Design",
  LLM08_AUTHORIZATION = "LLM08: Authorization Bypass",
  LLM09_OVERRELIANCE = "LLM09: Overreliance on Model",
  LLM10_MODEL_THEFT = "LLM10: Model Theft",
}

/**
 * Compliance Framework Mappings
 */
export enum FrameworkMapping {
  OWASP_ASI = "OWASP AI Security Standard",
  MITRE_ATLAS = "MITRE Adversarial Threat Landscape for AI Systems",
  NIST_AI_RMF = "NIST AI Risk Management Framework",
  ISO_42001 = "ISO/IEC 42001 AI Management System",
  EU_AI_ACT = "EU AI Act",
}

/**
 * Payload Complexity Levels
 */
export enum ComplexityLevel {
  BASIC = "basic",
  INTERMEDIATE = "intermediate",
  ADVANCED = "advanced",
  EXPERT = "expert",
}

/**
 * Risk Levels
 */
export enum RiskLevel {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  CRITICAL = "critical",
}

/**
 * Effectiveness Metrics for a Payload
 */
export interface EffectivenessMetrics {
  success_rate: number;
  total_attempts: number;
  last_used?: string;
  avg_detection_time_ms?: number;
  framework_success_rates: Record<string, number>;
}

/**
 * Payload Template Model
 */
export interface PayloadTemplate {
  id: string;
  name: string;
  slug: string;
  category: AttackCategory;
  subcategory?: string;
  complexity: ComplexityLevel;
  template: string;
  description: string;
  variables: string[];
  framework_mappings: Partial<Record<FrameworkMapping, string[]>>;
  target_frameworks: string[];
  target_models: string[];
  effectiveness_metrics?: EffectivenessMetrics;
  user_rating: number;
  user_feedback_count: number;
  tags: string[];
  author?: string;
  source?: string;
  references: string[];
  version: string;
  is_active: boolean;
  is_deprecated: boolean;
  deprecation_reason?: string;
  requires_secondary_confirmation: boolean;
  risk_level: RiskLevel;
  created_at: string;
  updated_at: string;
}

/**
 * Create Payload Request
 */
export interface PayloadTemplateCreate {
  name: string;
  slug?: string;
  category: AttackCategory;
  subcategory?: string;
  complexity: ComplexityLevel;
  template: string;
  description: string;
  variables?: string[];
  framework_mappings?: Partial<Record<FrameworkMapping, string[]>>;
  target_frameworks?: string[];
  target_models?: string[];
  tags?: string[];
  author?: string;
  source?: string;
  references?: string[];
  requires_secondary_confirmation?: boolean;
  risk_level?: RiskLevel;
}

/**
 * Update Payload Request
 */
export interface PayloadTemplateUpdate {
  name?: string;
  slug?: string;
  category?: AttackCategory;
  subcategory?: string;
  complexity?: ComplexityLevel;
  template?: string;
  description?: string;
  variables?: string[];
  framework_mappings?: Partial<Record<FrameworkMapping, string[]>>;
  target_frameworks?: string[];
  target_models?: string[];
  tags?: string[];
  is_active?: boolean;
  is_deprecated?: boolean;
  deprecation_reason?: string;
  version?: string;
  requires_secondary_confirmation?: boolean;
  risk_level?: RiskLevel;
}

/**
 * Search Filters
 */
export interface PayloadSearchFilters {
  category?: AttackCategory;
  subcategory?: string;
  complexity?: ComplexityLevel;
  target_framework?: string;
  target_model?: string;
  tags?: string[];
  risk_level?: RiskLevel;
  min_effectiveness?: number;
  framework_mapping?: FrameworkMapping;
}

/**
 * Render Payload Request
 */
export interface PayloadRenderRequest {
  template_id: string;
  variable_values: Record<string, unknown>;
  context?: string;
}

/**
 * Render Payload Response
 */
export interface PayloadRenderResponse {
  rendered_payload: string;
  template_id: string;
  template_name: string;
  warnings: string[];
  requires_confirmation: boolean;
  risk_level: RiskLevel;
  category: AttackCategory;
}

/**
 * API Response Wrapper
 */
export interface ApiResponse<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
  errors?: string[];
}

/**
 * Paginated Response
 */
export interface PaginatedResponse<T = unknown> {
  success: boolean;
  data: T[];
  total: number;
  page: number;
  per_page: number;
  has_more: boolean;
}

/**
 * Category Count Response
 */
export interface CategoryCounts {
  [categoryName: string]: number;
}

/**
 * Payload Library Client Class
 *
 * Provides methods to interact with the payload library API.
 */
export class PayloadLibraryClient {
  constructor(private baseUrl: string = "/api/v1") {}

  /**
   * List all payloads with pagination
   */
  async listPayloads(params: {
    limit?: number;
    offset?: number;
    active_only?: boolean;
  } = {}): Promise<PaginatedResponse<PayloadTemplate>> {
    const searchParams = new URLSearchParams();
    if (params.limit) searchParams.set("limit", params.limit.toString());
    if (params.offset) searchParams.set("offset", params.offset.toString());
    if (params.active_only !== undefined)
      searchParams.set("active_only", params.active_only.toString());

    const response = await fetch(`${this.baseUrl}/payloads/?${searchParams}`);
    return response.json();
  }

  /**
   * Search payloads using filters
   */
  async searchPayloads(
    filters: PayloadSearchFilters & { q?: string; limit?: number }
  ): Promise<PaginatedResponse<PayloadTemplate>> {
    const searchParams = new URLSearchParams();

    if (filters.q) searchParams.set("q", filters.q);
    if (filters.category) searchParams.set("category", filters.category);
    if (filters.subcategory) searchParams.set("subcategory", filters.subcategory);
    if (filters.complexity) searchParams.set("complexity", filters.complexity);
    if (filters.target_framework) searchParams.set("target_framework", filters.target_framework);
    if (filters.target_model) searchParams.set("target_model", filters.target_model);
    if (filters.tags) searchParams.set("tags", filters.tags.join(","));
    if (filters.risk_level) searchParams.set("risk_level", filters.risk_level);
    if (filters.min_effectiveness)
      searchParams.set("min_effectiveness", filters.min_effectiveness.toString());
    if (filters.framework_mapping) searchParams.set("framework_mapping", filters.framework_mapping);
    if (filters.limit) searchParams.set("limit", filters.limit.toString());

    const response = await fetch(`${this.baseUrl}/payloads/search?${searchParams}`);
    return response.json();
  }

  /**
   * Get a payload by ID
   */
  async getPayload(id: string): Promise<ApiResponse<PayloadTemplate>> {
    const response = await fetch(`${this.baseUrl}/payloads/${id}`);
    return response.json();
  }

  /**
   * Get a payload by slug
   */
  async getPayloadBySlug(slug: string): Promise<ApiResponse<PayloadTemplate>> {
    const response = await fetch(`${this.baseUrl}/payloads/slug/${slug}`);
    return response.json();
  }

  /**
   * Get payloads by category
   */
  async getPayloadsByCategory(
    category: AttackCategory,
    limit = 100
  ): Promise<ApiResponse<PayloadTemplate[]>> {
    const response = await fetch(
      `${this.baseUrl}/payloads/category/${category}?limit=${limit}`
    );
    return response.json();
  }

  /**
   * Get category counts
   */
  async getCategoryCounts(): Promise<ApiResponse<CategoryCounts>> {
    const response = await fetch(`${this.baseUrl}/payloads/categories`);
    return response.json();
  }

  /**
   * Render a payload template
   */
  async renderPayload(
    request: PayloadRenderRequest
  ): Promise<ApiResponse<PayloadRenderResponse>> {
    const response = await fetch(`${this.baseUrl}/payloads/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    return response.json();
  }

  /**
   * Record feedback for a payload
   */
  async addFeedback(payloadId: string, rating: number): Promise<ApiResponse> {
    const response = await fetch(
      `${this.baseUrl}/payloads/${payloadId}/feedback?rating=${rating}`,
      { method: "POST" }
    );
    return response.json();
  }

  /**
   * Create a new payload
   */
  async createPayload(
    payload: PayloadTemplateCreate
  ): Promise<ApiResponse<PayloadTemplate>> {
    const response = await fetch(`${this.baseUrl}/payloads/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return response.json();
  }

  /**
   * Update a payload
   */
  async updatePayload(
    id: string,
    updates: PayloadTemplateUpdate
  ): Promise<ApiResponse<PayloadTemplate>> {
    const response = await fetch(`${this.baseUrl}/payloads/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    return response.json();
  }

  /**
   * Delete a payload
   */
  async deletePayload(id: string, hardDelete = false): Promise<ApiResponse> {
    const response = await fetch(
      `${this.baseUrl}/payloads/${id}?hard_delete=${hardDelete}`,
      { method: "DELETE" }
    );
    return response.json();
  }
}
