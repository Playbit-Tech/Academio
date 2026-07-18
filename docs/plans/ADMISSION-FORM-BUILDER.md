# Dynamic Admission Form Builder — Phase Plan

> **Objective**: Build a school-specific dynamic application form system where each school can define multiple application forms with configurable fields, validation, and sections. The public application wizard renders dynamically from the form configuration.
> **Source**: AGENTS.md anchored summary + user requirements
> **Strategy**: Backend-first (models → API), then frontend (admin builder → public form)
> **Total Phases**: 5

---

## DEPENDENCY GRAPH

```
Phase 1 (Models + Migration)
  ├──► Phase 2 (Admin API)
  │       └──► Phase 4 (Frontend Form Builder)
  └──► Phase 3 (Public API)
          └──► Phase 5 (Frontend Dynamic Public Form)
```

Phases 2 and 3 depend only on Phase 1 and can run in parallel.
Phases 4 and 5 depend on their respective backend APIs and can also run in parallel.

---

## ARCHITECTURE OVERVIEW

### Entity Hierarchy

```
School
  └── ApplicationForm (e.g., "Primary Admission", "Secondary Admission")
        └── ApplicationFormField (text, select, date, file, etc.)
  └── AdmissionIntake ─── form_id ──► ApplicationForm
  └── Application
        ├── form_id ──► ApplicationForm
        ├── form_responses (JSONB — all answers)
        └── extracted columns (applicant_name, email, phone) from mapped fields
```

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Form storage | `ApplicationForm` + `ApplicationFormField` tables | Normalized, queryable, migratable |
| Field responses | `form_responses` JSONB on `Application` | Flexible, no schema changes per form, always loaded with app |
| Mapped columns | `MappedTo` field on `ApplicationFormField` | Enables extracted columns (name, email, phone) for fast listing/search |
| Form → Intake linkage | Optional `form_id` FK on `AdmissionIntake` | Intake can optionally use a form; backward-compatible |
| Multi-step wizard | Group by `section` field | Each section = one wizard step |
| Document fields | Fields with `type: "file"` grouped into a document upload step | Separate step in wizard for file upload UX |

---

## Phase 1: Backend Models + Migration

**Goal**: Add `ApplicationForm` and `ApplicationFormField` models, update `AdmissionIntake` and `Application`, create migration.

### Files to Modify

| File | Change |
|---|---|
| `backend/internal/database/models/admission.go` | Add `ApplicationForm`, `ApplicationFormField` models. Update `AdmissionIntake` with `FormID` field. Update `Application` with `FormID` + `FormResponses` fields |
| `backend/internal/database/migrations/school/school.go` | Add new tables to Group 13 `AutoMigrate`. Add new tables to `schoolIDTables` FK list |

### New Models

```go
// ApplicationForm defines a school-specific application form configuration.
type ApplicationForm struct {
    ID        uint           `gorm:"primaryKey" json:"id"`
    UUID      guuid.UUID     `gorm:"type:uuid;uniqueIndex;default:gen_random_uuid()" json:"uuid"`
    SchoolID  uint           `gorm:"index;not null" json:"school_id"`
    Name      string         `gorm:"size:255" json:"name"`
    Slug      string         `gorm:"uniqueIndex;size:255" json:"slug"`
    Status    string         `gorm:"size:20;default:'draft'" json:"status"` // draft, active, archived
    CreatedAt time.Time      `json:"created_at"`
    UpdatedAt time.Time      `json:"updated_at"`

    Fields []ApplicationFormField `gorm:"foreignKey:FormID" json:"fields,omitempty"`
}

func (ApplicationForm) TableName() string { return "application_forms" }

// ApplicationFormField defines a single field in an application form.
type ApplicationFormField struct {
    ID            uint       `gorm:"primaryKey" json:"id"`
    UUID          guuid.UUID `gorm:"type:uuid;uniqueIndex;default:gen_random_uuid()" json:"uuid"`
    FormID        uint       `gorm:"index;not null" json:"form_id"`
    FieldKey      string     `gorm:"size:100" json:"field_key"`
    Label         string     `gorm:"size:255" json:"label"`
    FieldType     string     `gorm:"size:50" json:"field_type"`  // text, textarea, select, radio, checkbox, date, file, number, email, phone
    Required      bool       `gorm:"default:false" json:"required"`
    Placeholder   string     `gorm:"size:255" json:"placeholder,omitempty"`
    DefaultValue  string     `gorm:"type:text" json:"default_value,omitempty"`
    Section       string     `gorm:"size:100" json:"section"`       // wizard step name
    SectionOrder  int        `gorm:"default:0" json:"section_order"`
    FieldOrder    int        `gorm:"default:0" json:"field_order"`
    Width         string     `gorm:"size:20;default:'full'" json:"width"` // full, half
    Options       *string    `gorm:"type:jsonb" json:"options,omitempty"`    // for select/radio/checkbox
    Validation    *string    `gorm:"type:jsonb" json:"validation,omitempty"` // e.g. {"min": 2, "max": 100, "pattern": "^..."}
    MappedTo      *string    `gorm:"size:50" json:"mapped_to,omitempty"`     // applicant_name, applicant_email, applicant_phone
    Enabled       bool       `gorm:"default:true" json:"enabled"`
    CreatedAt     time.Time  `json:"created_at"`
    UpdatedAt     time.Time  `json:"updated_at"`
}

func (ApplicationFormField) TableName() string { return "application_form_fields" }
```

### Model Updates

**AdmissionIntake** — add optional form link:
```go
FormID *uint `gorm:"index" json:"form_id,omitempty"`
Form   *ApplicationForm `gorm:"foreignKey:FormID" json:"-"`
```

**Application** — add form reference and responses:
```go
FormID        *uint    `gorm:"index" json:"form_id,omitempty"`
FormResponses *string  `gorm:"type:jsonb" json:"form_responses,omitempty"`
Form          *ApplicationForm `gorm:"foreignKey:FormID" json:"-"`
```

### Migration Changes

1. Add `models.ApplicationForm{}`, `models.ApplicationFormField{}` to Group 13 `AutoMigrate`
2. Add `"application_forms"`, `"application_form_fields"` to `schoolIDTables`

### Verification
- `go build ./...` passes
- `go vet ./...` passes

---

## Phase 2: Backend Admin API

**Goal**: CRUD endpoints for managing forms and fields. New DTOs, service methods, repository methods, and handler endpoints.

### Files to Modify

| File | Change |
|---|---|
| `backend/internal/modules/admission/dto.go` | Add `FormResponse`, `FormFieldResponse`, `CreateFormRequest`, `CreateFormFieldRequest`, `UpdateFormFieldRequest`, `FormListResponse`, `FormConfigResponse`. Update `IntakeResponse` with `FormID`. Update `CreateIntakeRequest` with `FormID` |
| `backend/internal/modules/admission/repository.go` | Add form/field CRUD methods to interface + implementation |
| `backend/internal/modules/admission/service.go` | Add form/field business logic methods |
| `backend/internal/modules/admission/handler.go` | Add admin handler methods for forms + fields |
| `backend/internal/router/router.go` | Register new form/field admin routes |

### New API Endpoints (Admin)

| Method | Endpoint | Handler | Purpose |
|---|---|---|---|
| `GET` | `/admissions/forms` | `ListForms` | List all forms for school |
| `POST` | `/admissions/forms` | `CreateForm` | Create a new form |
| `GET` | `/admissions/forms/:id` | `GetForm` | Get form with fields |
| `PUT` | `/admissions/forms/:id` | `UpdateForm` | Update form name/status |
| `DELETE` | `/admissions/forms/:id` | `DeleteForm` | Delete/archive a form |
| `POST` | `/admissions/forms/:id/fields` | `CreateField` | Add a field to a form |
| `PUT` | `/admissions/forms/fields/:id` | `UpdateField` | Update a field |
| `DELETE` | `/admissions/forms/fields/:id` | `DeleteField` | Remove a field |
| `PUT` | `/admissions/forms/:id/fields/reorder` | `ReorderFields` | Batch update field/section order |

### Updated Endpoints

| Endpoint | Change |
|---|---|
| `POST /admissions/intakes` | Accept optional `form_id` in request body |
| `PUT /admissions/intakes/:id` | Accept optional `form_id` in request body |
| `GET /admissions/intakes` / `GET /admissions/intakes/:id` | Include `form_id` and form name in response |
| `GET /admissions/applications/:id` | Include `form_id`, `form_slug`, `form_responses` in detail response |

### Key DTOs

```go
// FormResponse — admin view of a form
type FormResponse struct {
    ID        uint                `json:"id"`
    SchoolID  uint                `json:"school_id"`
    Name      string              `json:"name"`
    Slug      string              `json:"slug"`
    Status    string              `json:"status"`
    Fields    []FormFieldResponse `json:"fields,omitempty"`
    CreatedAt string              `json:"created_at"`
    UpdatedAt string              `json:"updated_at"`
}

// FormFieldResponse — admin view of a field
type FormFieldResponse struct {
    ID           uint                   `json:"id"`
    FormID       uint                   `json:"form_id"`
    FieldKey     string                 `json:"field_key"`
    Label        string                 `json:"label"`
    FieldType    string                 `json:"field_type"`
    Required     bool                   `json:"required"`
    Placeholder  string                 `json:"placeholder,omitempty"`
    DefaultValue string                 `json:"default_value,omitempty"`
    Section      string                 `json:"section"`
    SectionOrder int                    `json:"section_order"`
    FieldOrder   int                    `json:"field_order"`
    Width        string                 `json:"width"`
    Options      map[string]interface{} `json:"options,omitempty"`
    Validation   map[string]interface{} `json:"validation,omitempty"`
    MappedTo     string                 `json:"mapped_to,omitempty"`
    Enabled      bool                   `json:"enabled"`
    CreatedAt    string                 `json:"created_at"`
    UpdatedAt    string                 `json:"updated_at"`
}
```

### Verification
- `go build ./...` passes
- `go vet ./...` passes

---

## Phase 3: Backend Public API

**Goal**: Public endpoint to fetch form config for rendering. Updated `SubmitApplication` to accept dynamic form responses.

### Files to Modify

| File | Change |
|---|---|
| `backend/internal/modules/admission/dto.go` | Add `PublicFormConfigResponse`, update `SubmitApplicationRequest` with `FormSlug` + `FormResponses` |
| `backend/internal/modules/admission/service.go` | Add `GetPublicFormConfig` method. Update `SubmitApplication` to validate + process form responses |
| `backend/internal/modules/admission/handler.go` | Add `GetPublicFormConfig` handler. Update `SubmitApplication` handler |
| `backend/internal/router/router.go` | Register public form config route |

### New Public Endpoints

| Method | Endpoint | Handler | Purpose |
|---|---|---|---|
| `GET` | `/admissions/form/:slug` | `GetPublicFormConfig` | Get form definition for public rendering (only active forms, only enabled fields) |

### Updated Public Endpoints

| Endpoint | Change |
|---|---|
| `POST /admissions/applications` | Accept `form_slug` + `form_responses: Record<string, any>`. Validate required fields, types, and options. Extract mapped fields into `applicant_name`, `applicant_email`, `applicant_phone`. Store raw responses in `FormResponses` JSONB |

### Public Form Config DTO

```go
type PublicFormConfigResponse struct {
    Name     string                   `json:"name"`
    Slug     string                   `json:"slug"`
    Sections []FormSectionResponse    `json:"sections"`
}

type FormSectionResponse struct {
    Section      string                `json:"section"`
    SectionOrder int                   `json:"section_order"`
    Fields       []PublicFieldResponse `json:"fields"`
}

type PublicFieldResponse struct {
    FieldKey     string                 `json:"field_key"`
    Label        string                 `json:"label"`
    FieldType    string                 `json:"field_type"`
    Required     bool                   `json:"required"`
    Placeholder  string                 `json:"placeholder,omitempty"`
    DefaultValue string                 `json:"default_value,omitempty"`
    Width        string                 `json:"width"`
    Options      map[string]interface{} `json:"options,omitempty"`
    Validation   map[string]interface{} `json:"validation,omitempty"`
}
```

### Updated SubmitApplication Flow

1. Accept `form_slug` + `form_responses` map
2. Look up form by slug, validate it's active
3. For each field in form config:
   - Check required fields are present
   - Validate type (email format, number range, etc.)
   - Validate select/radio options match
   - Extract `mapped_to` fields into model columns
4. Store all responses in `FormResponses` JSONB
5. Store form reference via `FormID`
6. Create application record with extracted columns + form responses
7. Return application detail response including form responses

### Verification
- `go build ./...` passes
- `go vet ./...` passes

---

## Phase 4: Frontend Form Builder (Admin)

**Goal**: Admin interface to create and manage forms and fields. Table-based field editor (upgradable to DnD later).

### Files to Create/Modify

| File | Change |
|---|---|
| `frontend/src/lib/api/admissions.ts` | Add `FormSummary`, `FormDetail`, `FormFieldData`, `CreateFormData`, `CreateFormFieldData` types. Add form/field API calls to `admissionsAdminApi` |
| `frontend/src/lib/hooks/useAdmissions.ts` | Add `useForms`, `useForm`, `useCreateForm`, `useUpdateForm`, `useDeleteForm`, `useCreateField`, `useUpdateField`, `useDeleteField`, `useReorderFields` hooks |
| `frontend/src/components/admissions/FormFieldEditor.tsx` | **New**: Table-based field editor with add/edit/delete dialogs |
| `frontend/src/components/admissions/FormEditor.tsx` | **New**: Form editor wrapper — name/status + field editor |
| `frontend/src/components/admissions/IntakeForm.tsx` | Add `form_id` dropdown selector |
| `frontend/src/routes/_dashboard/admissions/forms.tsx` | **New**: Route page with forms list + create dialog |
| `frontend/src/routes/_dashboard/admissions/intakes.tsx` | Add form selector in intake create/edit dialogs |

### Route Structure
```
/admissions/forms          → list of forms
/admissions/forms/:id      → form editor (name + fields CRUD)
```

### FormFieldEditor Component

Table columns:
| Column | Description |
|---|---|
| Order | Numeric sort (text input, upgrade to drag handles later) |
| Key | `field_key` (readable identifier) |
| Label | Display label |
| Type | Badge showing field type |
| Section | Which wizard step |
| Required | Toggle switch |
| Actions | Edit/Delete buttons |

Dialogs:
- **Add Field**: Form with field_key, label, type dropdown, required toggle, section input, width (full/half), options (for select/radio), validation rules
- **Edit Field**: Same form prefilled
- **Delete**: Confirm dialog

### IntakeForm Update
Add `form_id` dropdown selector populated from `useForms` when creating/editing an intake.

### Verification
- `npx tsc --noEmit` passes
- `yarn build` passes

---

## Phase 5: Frontend Dynamic Public Form

**Goal**: Refactor the public `ApplicationForm` to render dynamically from the form config returned by the backend.

### Files to Modify

| File | Change |
|---|---|
| `frontend/src/components/admissions/ApplicationForm.tsx` | **Major refactor**: Fetch form config by slug, render sections as wizard steps, dynamically render each field type, submit `form_responses` |
| `frontend/src/components/admissions/PersonalInfoStep.tsx` | May become deprecated (fields rendered dynamically) |
| `frontend/src/components/admissions/ContactStep.tsx` | May become deprecated |
| `frontend/src/components/admissions/AcademicStep.tsx` | May become deprecated |
| `frontend/src/components/admissions/DocumentUpload.tsx` | Keep/reuse — handle file-type fields |
| `frontend/src/components/admissions/ReviewStep.tsx` | Update to render dynamic fields |
| `frontend/src/routes/_public/admissions/apply.tsx` | Accept `slug` search param to select form |

### Dynamic Rendering Logic

1. On mount, check `?slug=` search param → fetch form config via `GET /admissions/form/:slug`
2. Group fields by `section`, sorted by `section_order` → each section = one wizard step
3. Fields with `type: "file"` are grouped into a final document upload step
4. Render each field based on `field_type`:
   - `text` / `email` / `phone` / `number` → `<Input>`
   - `textarea` → `<Textarea>`
   - `select` → `<Select>` with options
   - `radio` → `<RadioGroup>`
   - `checkbox` → `<Checkbox>` group
   - `date` → `<Input type="date">`
   - `file` → `<FileUploadZone>` (in document step)
5. Apply validation from field config:
   - `required` → Zod `.min(1)` or `.nonempty()`
   - `options` → Zod `.refine(val => options.includes(val))`
   - `validation.min` / `validation.max` → Zod `.min()` / `.max()`
   - `validation.pattern` → Zod `.regex()`
6. On submit:
   - Build `form_responses: Record<string, any>` from all field values
   - Call `POST /admissions/applications` with `form_slug` + `form_responses`
   - Upload files separately by reference number

### URL-based form selection
```
/admissions/apply?slug=primary-admission   → renders Primary Admission form
/admissions/apply?slug=secondary-admission → renders Secondary Admission form
```
If no slug is provided, fetch all active intakes and let the user pick one → derive slug from intake's form.

### ApplicationForm Backward Compatibility
Keep `intake_id` + `form_slug` + `form_responses` as the new submission contract. The old hardcoded fields are removed from the submit request — instead they come from `form_responses` and are extracted server-side via `MappedTo`.

### Verification
- `npx tsc --noEmit` passes
- `yarn build` passes
- End-to-end: create form → add fields → create intake with form → apply via public form → view application in admin

---

## ROLLBACK PLAN

Per phase, if a phase fails verification:
1. **Model changes**: Revert model files, revert migration (remove tables from AutoMigrate + FK list)
2. **API changes**: Revert handler/service/repository additions, revert route registration
3. **Frontend changes**: Revert file changes, remove new routes
4. Run `go build ./...` or `yarn build` to confirm clean state

## AUDIT CHECKLIST (per `docs/architecture/10-AUDIT-CHECKLIST.md`)

- [ ] **Security**: Validate `form_slug` input, sanitize `form_responses` JSONB, ensure school-scoped access
- [ ] **Tenant isolation**: All form/field queries scoped by `school_id`
- [ ] **Input validation**: Validate field types, options, and required fields server-side
- [ ] **DB migrations**: Idempotent `AutoMigrate`, proper FK constraints
- [ ] **Backward compatibility**: Existing intakes without `form_id` continue to work; existing applications without `form_responses` continue to render
