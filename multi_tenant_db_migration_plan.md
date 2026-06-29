# SchoolCare Multi-Tenant Database Migration Plan

## Executive Summary

This document outlines the comprehensive migration plan for transforming the SchoolCare v2 platform from its current single-database architecture to a true multi-tenant database-per-school architecture. The plan builds upon the existing sophisticated multi-tenant foundation and implements complete data isolation while maintaining system performance, security, and scalability.

## Current Architecture Analysis

### Existing Strengths
✅ **Sophisticated Multi-Tenant Foundation**: Already implemented tenant management with plan-based feature control  
✅ **Clean Architecture**: Handler → Service → Repository layers  
✅ **Advanced Authentication**: JWT-based auth with RBAC  
✅ **Comprehensive Domain Models**: All school management modules with `SchoolID` isolation  
✅ **Modern Technology Stack**: Go/Gin, PostgreSQL, Redis, React/Vite  

### Current Limitations
❌ **Single Database**: All schools share one PostgreSQL database with `SchoolID` foreign key isolation  
❌ **No Database-Level Isolation**: Potential for data access issues between tenants  
❌ **Limited Scalability**: Performance bottlenecks with large tenant datasets  
❌ **No Per-Tenant Backups**: Cannot restore individual school data independently  

## Migration Objectives

### Primary Goals
1. **Complete Data Isolation**: Each school has its own dedicated PostgreSQL database
2. **Dynamic Connection Management**: Application connects to appropriate school database based on authenticated tenant
3. **Enhanced Security**: Zero data breaches between tenant databases
4. **Scalability**: Support 1000+ concurrent tenant connections
5. **Enterprise-Ready**: Comprehensive backup, monitoring, and error handling

### Success Metrics
- **Connection Performance**: <50ms tenant database connection time
- **Scalability**: Support 1000+ concurrent tenant connections
- **Reliability**: 99.9% uptime for tenant database connections
- **Security**: Zero data breaches between tenants
- **Backup Recovery**: RTO < 1 hour, RPO < 15 minutes
- **Provisioning Time**: <5 minutes for new school setup

## Technical Architecture

### Enhanced Core Database (`schoolcare_core`)

```sql
-- Enhanced schools table
ALTER TABLE schools ADD COLUMN 
    database_name VARCHAR(100) NOT NULL,
    database_host VARCHAR(255) NOT NULL DEFAULT 'localhost',
    database_port INTEGER NOT NULL DEFAULT 5432,
    database_username VARCHAR(100) NOT NULL,
    database_password_encrypted TEXT NOT NULL,
    database_status VARCHAR(20) NOT NULL DEFAULT 'active',
    connection_pool_size INTEGER NOT NULL DEFAULT 20,
    backup_schedule TEXT,
    last_backup TIMESTAMP;

-- New: Database connection management
CREATE TABLE database_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID REFERENCES schools(id),
    connection_string TEXT NOT NULL,
    encrypted_credentials TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- New: Backup management
CREATE TABLE tenant_backups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID REFERENCES schools(id),
    backup_name VARCHAR(255) NOT NULL,
    backup_path TEXT NOT NULL,
    size BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    restore_point TIMESTAMP
);
```

### School Database Structure

Each school will have its own database with the following naming convention:
- `school_{school_name}_{timestamp}` (e.g., `school_greenfield_1700000000`)

**School Database Schema** (all existing models with `SchoolID` foreign key):
- Students, Teachers, Parents, Staff
- Classes, Subjects, Timetable, Attendance
- Results, Fees, Payments, Accounting
- Library, Hostel, Transport, Inventory
- HR, Payroll, Documents

### Database Connection Manager

```go
type DatabaseConnectionManager struct {
    coreDB      *gorm.DB
    connections sync.Map // Cache for active connections
    encryptor   EncryptionService
    config      *Config
}

func (dcm *DatabaseConnectionManager) GetTenantDB(tenantID uuid.UUID) (*gorm.DB, error) {
    // Check cache first
    if cached, exists := dcm.connections.Load(tenantID); exists {
        return cached.(*gorm.DB), nil
    }
    
    // Get school config from core DB
    var school School
    if err := dcm.coreDB.First(&school, tenantID).Error; err != nil {
        return nil, fmt.Errorf("school not found: %w", err)
    }
    
    // Create new connection
    dbConfig := DatabaseConfig{
        DatabaseName:     school.DatabaseName,
        DatabaseHost:     school.DatabaseHost,
        DatabasePort:     school.DatabasePort,
        DatabaseUsername: school.DatabaseUsername,
        DatabasePassword: dcm.encryptor.Decrypt(school.DatabasePasswordEncrypted),
        ConnectionPool:   school.ConnectionPoolSize,
        SSLMode:          "require",
    }
    
    // Create and cache connection
    tenantDB, err := dcm.createConnection(dbConfig)
    if err != nil {
        return nil, err
    }
    
    dcm.connections.Store(tenantID, tenantDB)
    return tenantDB, nil
}
```

## Implementation Phases

### Phase 1: Core Database Setup (Weeks 1-3)

#### Week 1: Database Schema Enhancement
1. **Enhance Schools Table**
   - Add database connection fields
   - Set up encrypted credential storage
   - Create database_connections table
   - Implement tenant_backups table

2. **Database Encryption Service**
   ```go
   type EncryptionService struct {
       key []byte
   }
   
   func (es *EncryptionService) Encrypt(plaintext string) string {
       // AES-256 encryption implementation
   }
   
   func (es *EncryptionService) Decrypt(ciphertext string) string {
       // AES-256 decryption implementation
   }
   ```

3. **Database Configuration Management**
   - Update config structure for multi-database support
   - Add environment variables for database connection settings
   - Create database connection validation

#### Week 2: Database Connection Manager
1. **Implement DatabaseConnectionManager**
   - Connection pooling and caching
   - Automatic reconnection logic
   - Connection health checks
   - Performance monitoring

2. **Repository Factory Pattern**
   - Create RepositoryFactory for tenant-aware repositories
   - Implement dependency injection
   - Add connection lifecycle management

3. **Service Layer Integration**
   - Update existing services to use tenant-aware repositories
   - Implement tenant context injection
   - Add error handling for connection failures

#### Week 3: Testing and Validation
1. **Unit Testing**
   - Database connection manager tests
   - Repository factory tests
   - Encryption service tests
   - Service layer integration tests

2. **Integration Testing**
   - Multi-tenant connection testing
   - Performance testing with multiple tenants
   - Connection pool validation
   - Error scenario testing

### Phase 2: Repository Layer Refactoring (Weeks 4-6)

#### Week 4: Repository Pattern Enhancement
1. **Enhance Existing Repositories**
   - Modify repositories to accept tenant database connections
   - Add tenant-specific query methods
   - Implement pagination and filtering
   - Add comprehensive error handling

2. **Repository Factory Implementation**
   ```go
   type RepositoryFactory struct {
       dbManager *DatabaseConnectionManager
   }
   
   func (rf *RepositoryFactory) CreateTenantRepository(tenantID uuid.UUID, repoType string) (interface{}, error) {
       tenantDB, err := rf.dbManager.GetTenantDB(tenantID)
       if err != nil {
           return nil, err
       }
       
       switch repoType {
       case "user":
           return &UserRepository{db: tenantDB}, nil
       case "student":
           return &StudentRepository{db: tenantDB}, nil
       case "teacher":
           return &TeacherRepository{db: tenantDB}, nil
       case "finance":
           return &FinanceRepository{db: tenantDB}, nil
       default:
           return nil, fmt.Errorf("unknown repository type: %s", repoType)
       }
   }
   ```

#### Week 5: Service Layer Updates
1. **Update Service Layer**
   - Modify services to use repository factory
   - Implement tenant context injection
   - Add transaction management
   - Update business logic for multi-tenant operations

2. **Middleware Implementation**
   - Tenant context middleware
   - Authentication and authorization middleware
   - Request ID tracking
   - Logging middleware

#### Week 6: Testing and Validation
1. **Service Layer Testing**
   - Multi-tenant service testing
   - Transaction management testing
   - Error handling validation
   - Performance testing

2. **End-to-End Testing**
   - Complete user journey testing
   - Multi-tenant data isolation testing
   - Performance validation
   - Security testing

### Phase 3: Migration System (Weeks 7-8)

#### Week 7: Migration Management
1. **Separate Migration Types**
   - Create `/migrations/core` directory
   - Create `/migrations/school` directory
   - Implement MigrationService
   - Add migration rollback capabilities

2. **Migration Service Implementation**
   ```go
   type MigrationService struct {
       coreDB     *gorm.DB
       dbManager  *DatabaseConnectionManager
       migrator   *gorm.Migrator
   }
   
   func (ms *MigrationService) ApplyCoreMigrations() error {
       return ms.coreDB.AutoMigrate(
           &models.School{},
           &models.User{},
           &models.Role{},
           &models.Tenant{},
           // ... core entities
       )
   }
   
   func (ms *MigrationService) ApplySchoolMigrations(tenantDB *gorm.DB) error {
       return tenantDB.AutoMigrate(
           &models.Student{},
           &models.Teacher{},
           &models.Class{},
           &models.Subject{},
           &models.Session{},
           // ... school-specific entities
       )
   }
   ```

#### Week 8: Automated Migration Tools
1. **Migration Tools**
   - Create migration management CLI
   - Implement automated migration application
   - Add migration rollback capabilities
   - Create migration validation tools

2. **Tenant Migration Tools**
   - Implement `MigrateAllTenants()` function
   - Add parallel migration support
   - Create migration status tracking
   - Add migration failure handling

### Phase 4: Enhanced Authentication & Tenant Resolution (Weeks 9-10)

#### Week 9: Tenant Resolution Service
1. **Tenant Resolution Service**
   - Implement `TenantResolutionService`
   - Add JWT token validation
   - Implement tenant context caching
   - Add comprehensive error handling

2. **Enhanced Authentication Flow**
   ```go
   type TenantResolutionService struct {
       coreDB             *gorm.DB
       dbManager         *DatabaseConnectionManager
       cache             *redis.Client
       config            *Config
   }
   
   func (trs *TenantResolutionService) ResolveTenantFromToken(tokenString string) (*TenantContext, error) {
       // 1. Validate JWT token
       claims, err := trs.validateToken(tokenString)
       if err != nil {
           return nil, fmt.Errorf("invalid token: %w", err)
       }
       
       // 2. Get user from core database
       var user models.User
       if err := trs.coreDB.Preload("School").First(&user, claims.UserID).Error; err != nil {
           return nil, fmt.Errorf("user not found: %w", err)
       }
       
       // 3. Check school status
       if user.School.DatabaseStatus != "active" {
           return nil, fmt.Errorf("school account is disabled")
       }
       
       // 4. Check subscription status
       if user.School.SubscriptionStatus != "active" {
           return nil, fmt.Errorf("subscription expired")
       }
       
       // 5. Get tenant database connection
       tenantDB, err := trs.dbManager.GetTenantDB(user.School.ID)
       if err != nil {
           return nil, fmt.Errorf("failed to connect to tenant database: %w", err)
       }
       
       // 6. Cache tenant context
       tenantCtx := &TenantContext{
           TenantID:    user.School.ID,
           SchoolName:  user.School.Name,
           Database:    tenantDB,
           User:        &user,
           Permissions: claims.Roles,
           RequestID:   generateRequestID(),
       }
       
       return tenantCtx, nil
   }
   ```

#### Week 10: Error Handling and Logging
1. **Enhanced Error Handling**
   - Implement tenant-aware error types
   - Add comprehensive error codes
   - Create error handling middleware
   - Add error logging and monitoring

2. **Enhanced Logging**
   - Implement tenant-aware logging
   - Add request ID tracking
   - Create structured logging format
   - Add performance monitoring

### Phase 5: Backup and Recovery System (Weeks 11-12)

#### Week 11: Backup Service Implementation
1. **Backup Service**
   - Implement `BackupService`
   - Create automated backup scheduling
   - Add backup validation
   - Implement backup compression

2. **Backup Management**
   ```go
   type BackupService struct {
       coreDB     *gorm.DB
       dbManager  *DatabaseConnectionManager
       s3Client   *s3.Client
       config     *Config
   }
   
   func (bs *BackupService) CreateTenantBackup(tenantID uuid.UUID) error {
       // 1. Get tenant database
       tenantDB, err := bs.dbManager.GetTenantDB(tenantID)
       if err != nil {
           return fmt.Errorf("failed to connect to tenant database: %w", err)
       }
       
       // 2. Create backup file name
       timestamp := time.Now().Format("20060102_150405")
       backupName := fmt.Sprintf("school_%s_backup_%s.sql", tenantID, timestamp)
       
       // 3. Create backup using pg_dump
       backupPath := fmt.Sprintf("/tmp/%s", backupName)
       cmd := exec.Command("pg_dump", 
           fmt.Sprintf("--host=%s", bs.config.Database.Host),
           fmt.Sprintf("--port=%d", bs.config.Database.Port),
           fmt.Sprintf("--username=%s", bs.config.Database.Username),
           "--no-password",
           "--format=custom",
           "--file="+backupPath,
           fmt.Sprintf("school_%s", tenantID),
       )
       
       if err := cmd.Run(); err != nil {
           return fmt.Errorf("failed to create backup: %w", err)
       }
       
       // 4. Upload to S3
       if err := bs.uploadToS3(backupPath, backupName); err != nil {
           return fmt.Errorf("failed to upload backup: %w", err)
       }
       
       return nil
   }
   ```

#### Week 12: Restore and Recovery
1. **Restore Service**
   - Implement restore functionality
   - Create automated restore tools
   - Add restore validation
   - Implement point-in-time recovery

2. **Testing and Validation**
   - Backup and restore testing
   - Recovery time validation
   - Data integrity testing
   - Performance impact testing

### Phase 6: Testing and Validation (Weeks 13-14)

#### Week 13: Comprehensive Testing
1. **Integration Testing**
   - Multi-tenant integration testing
   - Performance testing with multiple tenants
   - Security validation
   - Backup and restore testing

2. **Load Testing**
   - Concurrent tenant connection testing
   - Database performance testing
   - Memory usage validation
   - Network latency testing

#### Week 14: Final Validation
1. **System Validation**
   - End-to-end testing
   - User acceptance testing
   - Performance validation
   - Security validation

2. **Documentation and Training**
   - Create technical documentation
   - Create user guides
   - Create deployment guides
   - Create troubleshooting guides

## Risk Assessment and Mitigation

### High-Risk Items
1. **Data Migration Risk**
   - **Risk**: Data loss during migration
   - **Mitigation**: Comprehensive backup strategy, rollback procedures, validation testing

2. **Performance Risk**
   - **Risk**: Performance degradation during migration
   - **Mitigation**: Gradual migration approach, performance monitoring, load testing

3. **Data Isolation Risk**
   - **Risk**: Data leakage between tenants
   - **Mitigation**: Comprehensive testing, access controls, audit logging

### Medium-Risk Items
1. **Compatibility Risk**
   - **Risk**: Breaking changes to existing functionality
   - **Mitigation**: Backward compatibility testing, gradual rollout

2. **Operational Risk**
   - **Risk**: Operational complexity increase
   - **Mitigation**: Automation, monitoring, documentation

### Low-Risk Items
1. **Training Risk**
   - **Risk**: Staff unfamiliarity with new system
   - **Mitigation**: Training programs, documentation, support

## Deployment Strategy

### Staged Rollout
1. **Phase 1: Pilot Schools (Week 15)**
   - Select 3-5 pilot schools
   - Deploy to staging environment
   - Conduct user acceptance testing
   - Gather feedback and make adjustments

2. **Phase 2: Limited Rollout (Week 16-17)**
   - Deploy to 10-20 schools
   - Monitor performance and stability
   - Provide enhanced support
   - Gather feedback

3. **Phase 3: Full Rollout (Week 18+)**
   - Deploy to all schools
   - Monitor system performance
   - Provide ongoing support
   - Continuous improvement

### Rollback Strategy
1. **Rollback Triggers**
   - Critical performance issues
   - Data integrity issues
   - Security vulnerabilities
   - User acceptance failure

2. **Rollback Procedures**
   - Database rollback scripts
   - Configuration rollback
   - Data restoration procedures
   - Communication plan

## Monitoring and Maintenance

### Performance Monitoring
1. **Database Performance**
   - Connection pool metrics
   - Query performance
   - Memory usage
   - Disk I/O

2. **Application Performance**
   - Response times
   - Error rates
   - Throughput
   - Resource utilization

### Security Monitoring
1. **Access Control**
   - User authentication
   - Authorization checks
   - Audit logging
   - Intrusion detection

2. **Data Security**
   - Encryption monitoring
   - Backup validation
   - Data access patterns
   - Compliance monitoring

### Operational Monitoring
1. **System Health**
   - Service availability
   - Resource utilization
   - Error rates
   - Performance metrics

2. **Business Metrics**
   - User satisfaction
   - System adoption
   - Support ticket volume
   - Performance SLAs

## Future Enhancements

### Phase 7: BitReactor Integration (Weeks 19-20)
1. **Authentication Integration**
   - Replace JWT with BitReactor auth
   - Implement BitReactor token validation
   - Add BitReactor user management

2. **Tenant Management Integration**
   - Replace tenant management with BitReactor APIs
   - Implement BitReactor subscription management
   - Add BitReactor billing integration

3. **API Gateway Integration**
   - Implement BitReactor API gateway
   - Add rate limiting
   - Implement API monitoring

### Phase 8: Advanced Features (Weeks 21-22)
1. **Advanced Analytics**
   - Multi-tenant reporting
   - Performance analytics
   - User behavior analytics
   - Business intelligence

2. **Advanced Monitoring**
   - Real-time monitoring
   - Predictive analytics
   - Automated scaling
   - Advanced alerting

## Budget and Resources

### Development Resources
- **Backend Developers**: 4 developers (6 months)
- **Frontend Developers**: 2 developers (3 months)
- **DevOps Engineers**: 2 engineers (4 months)
- **QA Engineers**: 2 engineers (4 months)
- **Project Manager**: 1 manager (6 months)

### Infrastructure Resources
- **Database Servers**: 2 servers (primary + standby)
- **Application Servers**: 4 servers (load balanced)
- **Storage**: 500GB SSD for databases
- **Backup Storage**: 1TB cloud storage
- **Monitoring Tools**: Prometheus, Grafana, ELK stack

### Training and Documentation
- **Technical Documentation**: 2 weeks
- **User Training**: 1 week
- **Admin Training**: 1 week
- **Support Documentation**: 1 week

## Success Criteria

### Technical Success Criteria
1. **Database Isolation**: Complete data separation between schools
2. **Performance**: <50ms connection time, 99.9% uptime
3. **Scalability**: Support 1000+ concurrent tenant connections
4. **Security**: Zero data breaches between tenants
5. **Backup Recovery**: RTO < 1 hour, RPO < 15 minutes

### Business Success Criteria
1. **User Satisfaction**: >95% user satisfaction rating
2. **System Adoption**: >90% of schools migrated within 3 months
3. **Performance Improvement**: 50% improvement in system performance
4. **Operational Efficiency**: 40% reduction in operational overhead
5. **Cost Efficiency**: 30% reduction in infrastructure costs

## Conclusion

This comprehensive migration plan provides a clear, actionable path to achieve true multi-tenant database isolation while maintaining the sophisticated features and clean architecture of the SchoolCare v2 platform. The plan is designed to minimize risk, ensure data integrity, and provide a scalable, secure, and maintainable solution for thousands of schools.

The phased approach allows for gradual implementation, thorough testing, and continuous improvement while maintaining system availability and performance. The plan also includes provisions for future enhancements, including BitReactor integration and advanced analytics capabilities.

By following this plan, SchoolCare will achieve enterprise-grade multi-tenant architecture that supports complete data isolation, enhanced security, and improved scalability for future growth.