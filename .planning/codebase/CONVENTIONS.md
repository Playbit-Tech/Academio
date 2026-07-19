# Coding Conventions

**Analysis Date:** 2026-07-18

---

## Go Conventions

### Project Structure

**Module Layout** (per `backend/internal/modules/`):
Each module follows a consistent four-file layout:
- `dto.go` — Request/response DTOs with `json` struct tags and `binding` validation tags
- `handler.go` — HTTP handler with Gin `*gin.Context`, route parsing, response formatting
- `service.go` — Business logic with named `*Service` struct and `New*Service` constructor
- `repository.go` — Data access with GORM, repository interface defined at top

```
internal/modules/user/
├── dto.go
├── handler.go
├── repository.go
└── service.go
```

**Repository Interface Pattern:**
Interfaces are defined at the top of `repository.go` for testability. Each method takes `ctx context.Context` as the first parameter. Concrete repository structs embed `*gorm.DB`.

```go
// Repository interface (top of repository.go)
type UserRepositoryInterface interface {
    Create(ctx context.Context, user *models.User) error
    FindByID(ctx context.Context, id uint) (*models.User, error)
    // ...
}

// Concrete implementation
type UserRepository struct {
    db         *gorm.DB
    schemaName string
}
```

**Service constructor pattern:**
```go
type UserService struct {
    userRepo UserRepositoryInterface
}

func NewUserService(userRepo UserRepositoryInterface) *UserService {
    return &UserService{userRepo: userRepo}
}
```

**Handler constructor pattern:**
```go
type UserHandler struct {
    userService    *UserService
    studentService *StudentService
    // ...
}

func NewUserHandler(/* deps */) *UserHandler {
    return &UserHandler{/* ... */}
}
```

### Naming Conventions

| Construct | Convention | Example |
|---|---|---|
| Files | camelCase | `service.go`, `dto.go`, `handler.go` |
| Exported functions | PascalCase | `CreateUserWithChecks` |
| Unexported functions | camelCase | `findOrCreateParentUserInCore` |
| Service/Handler types | PascalCase | `UserService`, `UserHandler` |
| Interfaces | Meaningful `Interface` suffix | `UserRepositoryInterface` |
| Error vars | `Err` prefix | `ErrNotFound`, `ErrConflict` |
| Constants | PascalCase | `MaxPageSize`, `RoleParent` |
| Abbreviations | Keep case | `schoolID`, `userURL` |
| Receivers | 1-2 letter abbreviation | `s *UserService`, `r *UserRepository` |

### Import Organization

Imports grouped in three blocks separated by blank lines:
1. Standard library
2. Third-party (including GORM, Gin, Redis)
3. Internal modules (`github.com/playbits/schoolcare-v2/...`)

```go
import (
    "context"
    "fmt"
    "strings"

    "gorm.io/gorm"
    "github.com/gin-gonic/gin"

    "github.com/playbits/schoolcare-v2/internal/database/models"
    "github.com/playbits/schoolcare-v2/pkg/logger"
)
```

### Error Handling

**Error wrapping:** Use `fmt.Errorf("context: %w", err)` to wrap errors in service/repository layers.

```go
// Service layer
return nil, fmt.Errorf("create student: %w", err)

// Domain errors use internal errors package
return nil, domerr.NewNotFoundError("user")
```

**Error handling patterns (from AGENTS.md / STYLE.md):**

| Context | Strategy | Rationale |
|---|---|---|
| Analytics/reports queries | Log warning, continue | Best-effort analytics |
| State mutations | Return error | Silent failures corrupt status |
| Batch operations | Collect all errors, return one message | Better UX — user fixes everything in one pass |

**Domain error types** (`internal/errors/errors.go`):
- `NewNotFoundError(entity string)` — 404
- `NewConflictError(msg string)` — 409
- `NewForbiddenError(msg string)` — 403
- `NewUnauthorizedError(msg string)` — 401
- `NewBadRequestError(msg string)` — 400
- `NewValidationError(msg string)` — 422
- Each has `.Code`, `.Category`, `.Message`, `.StatusCode()` fields

### GORM/ORM Patterns

**Model definitions** (`internal/database/models/`):
- Use `BaseModel` to embed `ID`, `UUID`, `CreatedAt`, `UpdatedAt`, `DeletedAt`
- Tag columns with `gorm` and `json` tags
- `many2many` relationships use `gorm:"many2many:table_name;"`
- Always scope queries to tenant schema via `middleware.GetTenantDB(c *gin.Context)` returning `*gorm.DB` with `SchemaTablePrefix`

```go
type Student struct {
    BaseModel
    UserID   uint   `gorm:"uniqueIndex;not null" json:"user_id"`
    SchoolID uint   `gorm:"index;not null" json:"school_id"`
    LevelID  uint   `gorm:"index;not null" json:"level_id"`
    Level    *Level `gorm:"foreignKey:LevelID" json:"-"`
}
```

**Query patterns:**
- List queries always capped with page limit, default 100, max 1000
- Multi-statement `db.Exec()` forbidden — break into individual calls
- Use `Select(...)` to scope updates (avoid many2many join tables)
- Parameterized queries always via GORM — never `fmt.Sprintf` for SQL

**Preload usage** (e.g., timetables):
```go
// Repository preloads resolved names for display
db.Preload("Subject").Preload("Teacher.UserInfo").Preload("Level").Find(&entries)
```

### Middleware Patterns

**Middleware** functions in `internal/middleware/`:
- `GetTenantDB(c *gin.Context)` — returns schema-scoped `*gorm.DB`
- `GetRole(c *gin.Context)` — returns role string from JWT context
- `requireAdminOrAbove(c *gin.Context) bool` — role guard in handlers (sends 403 if unauthorized)

### Context Propagation

All handler → service → repository chains accept `context.Context`:
```go
// Handler: c.Request.Context()
// Service: func (s *Service) GetUser(ctx context.Context, id uint) (*User, error)
// Repository: func (r *Repository) FindByID(ctx context.Context, id uint) (*User, error)
// Tenant DB: db.WithContext(ctx).First(&user, id)
```

### Logging

Use `pkg/logger` (slog wrapper):
```go
logger.Infof("Processing score entry", "student_id", studentID)
logger.Warnf("something happened: %v", err)
logger.Errorf("failed to process: %v", err)
```

Never use `fmt.Printf`, `log.Printf`, or `println`.

### Configuration

- `internal/config/` — loads from env vars via `os.Getenv`, validated at startup
- `.env` file at `backend/.env`
- `DSN()` uses `net/url` for safe DSN construction
- No hardcoded secrets

### Tests

**Table-driven tests with testify:**
```go
func TestBatchCreateStudents_DuplicateEmail_SkipsDuplicate(t *testing.T) {
    t.Parallel()
    // Arrange
    db := setupTestDB(t)
    // Act
    result, err := service.BatchCreateStudents(ctx, db, req)
    // Assert
    assert.NoError(t, err)
    require.Len(t, result, 2)
}
```

**Mock pattern:** Interface-based mocks in `mock_repository_test.go` within each module package, using `testify/mock`.

### Common Go Anti-Patterns (Forbidden)

```go
// ❌ Silent error discard
val, _ := doSomething()

// ❌ context.Background() in request scope
db.WithContext(context.Background()).Find(&x)

// ❌ Hardcoded credential / fallback secret
secret := "default-secret"

// ❌ fmt.Printf / log.Print in application code
fmt.Printf("user logged in: %d", userID)

// ❌ Multi-statement db.Exec (pgx v5 incompatibility)
db.Exec("CREATE TABLE t1; CREATE TABLE t2")

// ❌ Unbounded queries (no limit)
db.Model(&User{}).Find(&users)

// ❌ Unconditional Updates (no WHERE)
db.Model(&User{}).Update("name", "new name")

// ❌ fmt.Sprintf for SQL
db.Exec(fmt.Sprintf("SELECT * FROM users WHERE id = %s", userInput))
```

---

## TypeScript/React Conventions

### Component Patterns

**Function components only** — no class components. Files use PascalCase names in `kebab-case` directories:

```
src/components/timetable/calendar-grid.tsx
src/components/timetable/bulk-toolbar.tsx
src/components/admissions/ApplicationForm.tsx
```

**Default exports** for route components, named exports for others.

### Route Structure (TanStack Router)

File-based routing under `src/routes/`:
```
src/routes/
├── __root.tsx          # Root layout with <Toaster />
├── _dashboard/         # Dashboard routes (layout group)
│   ├── timetable.tsx
│   ├── attendance.tsx
│   ├── users.tsx
│   └── ...
└── login.tsx
```

Route definition pattern:
```tsx
export const Route = createFileRoute("/_dashboard/timetable")({
    beforeLoad: requireRole(["admin", "super-admin", "super_admin", "principal"]),
    component: TimetablePage,
});
```

Route guards via `requireRole()` in `src/lib/auth/route-guard.ts`.

### Hooks and API Client

**API client** (`src/lib/api.ts`):
- Single fetch-based client with Bearer token auth
- Automatic 401 → refresh → retry
- Methods: `api.get<T>()`, `api.post()`, `api.put()`, `api.delete()`
- Returns typed response: `ApiEnvelope<T>` with `{ success, data, error, meta }`

**TanStack Query hooks** in `src/lib/hooks/use*.ts` files (camelCase):
```ts
export function useTimetable(filters?: TimetableFilters) {
    return useQuery<TimetableEntry[]>({
        queryKey: [...queryKeys.timetable, filters],
        queryFn: () => api.get(`/timetables?...`),
    });
}
```

**Centralized query keys** in `src/lib/hooks/query-keys.ts`:
```ts
export const queryKeys = {
    users: ["users"] as const,
    user: (id: number) => ["users", id] as const,
    timetable: ["timetable"] as const,
    // ...
};
```

**Mutation pattern:**
```ts
const createMutation = useMutation({
    mutationFn: (data) => api.post("/endpoint", data),
    onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: queryKeys.timetable });
        toast.success("Created");
    },
    onError: () => toast.error("Failed"),
});
```

### Form Patterns (react-hook-form + Zod)

Schema definition:
```ts
const formSchema = z.object({
    name: z.string().optional(),
    session_id: z.string().min(1, "Session is required"),
    // ...
});

type FormValues = z.infer<typeof formSchema>;
```

Form hook:
```ts
const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { /* ... */ },
});
```

Form rendering with shadcn/ui form components:
```tsx
<FormField
    control={form.control}
    name="session_id"
    render={({ field }) => (
        <FormItem>
            <FormLabel>Session</FormLabel>
            <FormControl>
                <Select onValueChange={field.onChange} value={field.value}>
                    {/* ... */}
                </Select>
            </FormControl>
            <FormMessage />
        </FormItem>
    )}
/>
```

### UI Component Library

- **shadcn/ui** components in `src/components/ui/` (client components)
- Icons from `lucide-react`
- Toast notifications via `sonner`
- Tables via `@tanstack/react-virtual` and custom `DataTable` component

### Custom Hooks Pattern

Hooks live in `src/lib/hooks/` with `use` prefix:
- `useTimetable()` — fetches timetable entries
- `useSchool()` / `useSchools()` / `useCreateSchool()` — school CRUD
- `useSessions()` — academic sessions
- `useSubjects()` — school subjects
- `useClasses()` — class/level data

Each hook uses `api.*` and `queryKeys` from the centralized modules.

### Styling (Tailwind CSS)

- Use `cn()` utility (`clsx` + `tailwind-merge`) for conditional classes
- shadcn/ui CSS variables for theming (`--primary`, `--muted-foreground`, etc.)
- `text-muted-foreground` for secondary text
- `animate-spin` for loading states

### Imports Organization

Ordered by:
1. React/Router imports
2. Library imports (react-hook-form, zod, TanStack, shadcn)
3. Internal imports (`@/lib/*`, `@/components/*`, `@/stores/*`)
4. Relative imports

---

*Convention analysis: 2026-07-18*
