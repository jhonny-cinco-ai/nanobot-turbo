# Nanofolks Go Security Architecture

**Version:** 1.1  
**Date:** 2026-02-16  
**Focus:** API Key Protection & Deterministic LLM Access

## Executive Summary

This document outlines a defense-in-depth security architecture for Nanofolks Go that protects API keys from:
1. **Accidental exposure** to LLMs through prompts/context
2. **Memory dumps** and process inspection
3. **Configuration file theft**
4. **Malicious code execution** by LLM agents

**Key Innovation: Symbolic Key References**

Unlike traditional approaches where API keys are sanitized after exposure, Nanofolks Go uses **symbolic key references**. LLMs never see actual keys—only symbolic names like `{{openrouter_key}}`. Keys are resolved at execution time and never appear in context, logs, or memory accessible to the LLM.

The architecture uses multiple layers: symbolic references, encrypted storage, secure execution, and audit logging.

---

## 1. Core Security Innovation: Symbolic Key References

### 1.1 The Problem with Traditional Approaches

**Current approaches (like Python nanobot):**
```
Config: api_key = "sk-or-v1-abc123..."
   ↓
AgentLoop stores in memory
   ↓
WebSearchTool(api_key="sk-or-v1-abc123...") receives actual key
   ↓
LLM context might see key if logged/output
   ↓
Sanitizer masks it reactively
```

**Problems:**
- Keys exposed throughout the system
- Sanitizers can miss edge cases
- Keys visible in memory dumps
- Audit logs need complex masking

### 1.2 Symbolic Reference Architecture

**Nanofolks Go approach:**
```
Config: api_key = "sk-or-v1-abc123..." stored in KeyVault
   ↓
LLM Context sees: "Available keys: {{openrouter_key}}, {{brave_key}}"
   ↓
LLM wants to use tool with: key="{{openrouter_key}}"
   ↓
ToolExecutor resolves {{openrouter_key}} → actual value at execution time
   ↓
Key never exposed to LLM, logs, or context
```

### 1.3 Benefits

| Aspect | Traditional | Symbolic References |
|--------|-------------|---------------------|
| **Key in context** | Actual value, then masked | Never present |
| **Tool parameters** | Receive key strings | Receive symbolic names |
| **Execution** | Direct usage | Resolved at last moment |
| **Audit logs** | Must sanitize | Naturally safe |
| **Memory exposure** | Keys in process memory | Isolated in vault |
| **Rotation tracking** | Hard to track | Easy by reference |

---

## 2. Threat Model

### 1.1 Threats We're Protecting Against

| Threat | Risk Level | Description |
|--------|-----------|-------------|
| **LLM Prompt Injection** | 🔴 Critical | Attacker tricks LLM into revealing keys via crafted prompts |
| **Memory Scraping** | 🔴 Critical | Keys exposed in memory dumps, core dumps, swap |
| **Config File Extraction** | 🟠 High | Keys stolen from config files or backups |
| **Agent Tool Abuse** | 🟠 High | LLM uses tools to exfiltrate keys |
| **Screen/Log Capture** | 🟡 Medium | Keys visible in logs, UI, or screenshots |
| **Clipboard Snooping** | 🟡 Medium | Keys captured from clipboard history |

### 1.2 What We Accept

- **User has root access**: We can't protect against the user themselves
- **Physical access**: We assume the machine isn't compromised at hardware level
- **LLM providers**: We trust OpenAI, Anthropic, etc. (they see the keys anyway when we call them)

---

## 3. Security Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    NANOFOLKS SECURITY ZONES                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ZONE 1: UNTRUSTED (LLM Accessible)                         │
│  ├─ LLM Agents                                              │
│  ├─ System Prompts / Context                                │
│  ├─ Tool Descriptions (with {{key_refs}})                  │
│  ├─ Logs & UI                                               │
│  ├─ Chat History                                            │
│  └─ Audit Trail (references only)                           │
│                                                             │
│  ZONE 2: RESTRICTED (Execution Only)                        │
│  ├─ KeyVault with symbolic resolution                       │
│  ├─ ToolExecutor (resolves keys at runtime)                 │
│  ├─ Secure Memory Buffers                                   │
│  ├─ Rate-Limited API Client                                 │
│  └─ Audit Logger (references only)                          │
│                                                             │
│  ZONE 3: TRUSTED (Isolated Storage)                         │
│  ├─ OS Keyring                                              │
│  ├─ Encrypted Key Store                                     │
│  ├─ Hardware Security (TPM/Secure Enclave)                 │
│  └─ User Authentication                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Key Flow:
  ZONE 1 sees: {{openrouter_key}} (symbolic reference)
       ↓
  ZONE 2 resolves: {{openrouter_key}} → SecureString("sk-or-v1-...")
       ↓
  ZONE 2 uses: SecureString for API call
       ↓
  ZONE 2 wipes: SecureString.Destroy()
       ↓
  ZONE 1 audit: "Used key: openrouter_key" (reference only)
```

---

## 4. Layer 0: Symbolic Key References (Core Innovation)

### 4.1 KeyVault Implementation

The KeyVault is the central secure storage that never exposes actual keys to the LLM context.

```go
package security

import (
    "fmt"
    "strings"
    "sync"
)

// KeyVault holds all secrets, never exposes to LLM
type KeyVault struct {
    keys map[string]*SecureString  // "openrouter" -> SecureString
    mu   sync.RWMutex
}

// NewKeyVault creates a new key vault
func NewKeyVault() *KeyVault {
    return &KeyVault{
        keys: make(map[string]*SecureString),
    }
}

// Register adds a key to the vault
func (kv *KeyVault) Register(name string, key *SecureString) {
    kv.mu.Lock()
    defer kv.mu.Unlock()
    kv.keys[name] = key
}

// GetForExecution returns key for tool execution only
// This is the ONLY way to access actual key values
func (kv *KeyVault) GetForExecution(keyRef string) (*SecureString, error) {
    // Normalize: remove {{ and }}
    keyName := strings.Trim(keyRef, "{}")
    
    kv.mu.RLock()
    defer kv.mu.RUnlock()
    
    if key, exists := kv.keys[keyName]; exists {
        return key, nil
    }
    return nil, fmt.Errorf("key reference '%s' not found", keyName)
}

// GetPublicView returns what LLM sees (symbolic names only)
func (kv *KeyVault) GetPublicView() map[string]string {
    kv.mu.RLock()
    defer kv.mu.RUnlock()
    
    view := make(map[string]string)
    for name := range kv.keys {
        view[name] = fmt.Sprintf("{{%s}}", name)
    }
    return view
}

// ListKeyReferences returns list of available key references
func (kv *KeyVault) ListKeyReferences() []string {
    kv.mu.RLock()
    defer kv.mu.RUnlock()
    
    refs := make([]string, 0, len(kv.keys))
    for name := range kv.keys {
        refs = append(refs, fmt.Sprintf("{{%s}}", name))
    }
    return refs
}
```

### 4.2 ToolContext with Symbolic Resolution

Tools receive symbolic references and resolve them at execution time.

```go
// ToolContext provides secure access to keys during execution
type ToolContext struct {
    KeyVault *KeyVault
    Params   map[string]interface{}
}

// ResolveKey takes a parameter value and resolves symbolic references
func (tc *ToolContext) ResolveKey(value string) (*SecureString, error) {
    // Check if it's a symbolic reference {{key_name}}
    if strings.HasPrefix(value, "{{") && strings.HasSuffix(value, "}}") {
        return tc.KeyVault.GetForExecution(value)
    }
    
    // If not symbolic, treat as literal (for testing/debugging)
    // In production, this path should be disabled
    return NewSecureString(value), nil
}

// Example: WebSearchTool using symbolic keys
type WebSearchTool struct {
    KeyVault *KeyVault
}

func (t *WebSearchTool) Execute(ctx context.Context, params ToolParams) (ToolResult, error) {
    // LLM passes: api_key = "{{brave_key}}"
    keyRef := params.GetString("api_key")
    
    // Resolve at execution time - this is when the actual key is accessed
    apiKey, err := t.KeyVault.GetForExecution(keyRef)
    if err != nil {
        return ToolResult{}, fmt.Errorf("API key not configured: %s", keyRef)
    }
    defer apiKey.Destroy() // Ensure cleanup
    
    // Make actual API call with real key
    // Key is only in memory for this brief period
    resp, err := makeAPIRequest("https://api.brave.com/search", 
        header("Authorization", "Bearer "+apiKey.String()))
    
    return ToolResult{Data: resp}, nil
}
```

### 4.3 Context Building with Symbolic References

System prompts include symbolic references, not actual keys.

```go
// SecureContextBuilder builds context without exposing keys
type SecureContextBuilder struct {
    KeyVault *KeyVault
    sanitizer *SecretSanitizer  // Defense in depth
}

func (cb *SecureContextBuilder) BuildSystemPrompt() string {
    var parts []string
    
    // Tool descriptions show key requirements symbolically
    parts = append(parts, "# Available Tools")
    parts = append(parts, cb.getToolDescriptions())
    
    // Available API keys section
    parts = append(parts, "# Available API Keys")
    parts = append(parts, "When calling tools that require API keys, use these symbolic references:")
    parts = append(parts, "")
    
    for name, ref := range cb.KeyVault.GetPublicView() {
        parts = append(parts, fmt.Sprintf("- %s: %s (configured)", name, ref))
    }
    
    parts = append(parts, "")
    parts = append(parts, "Example: To use web search, pass api_key=\"{{brave_key}}\"")
    
    return strings.Join(parts, "\n")
}

// Example output to LLM:
// # Available API Keys
// When calling tools that require API keys, use these symbolic references:
//
// - openrouter: {{openrouter_key}} (configured)
// - brave: {{brave_key}} (configured)
// - anthropic: {{anthropic_key}} (configured)
//
// Example: To use web search, pass api_key="{{brave_key}}"
```

### 4.4 Audit Logging with References

Audit logs never contain actual keys—only symbolic references.

```go
// SecureAuditLogger tracks usage without exposing keys
type SecureAuditLogger struct {
    db *sql.DB
}

type AuditEntry struct {
    Timestamp   time.Time
    Operation   string
    KeyRef      string    // "{{openrouter_key}}" - never the actual key
    Endpoint    string
    Success     bool
}

func (al *SecureAuditLogger) LogToolExecution(toolName string, keyRef string, success bool) error {
    entry := AuditEntry{
        Timestamp: time.Now(),
        Operation: toolName,
        KeyRef:    keyRef,  // Symbolic reference only
        Success:   success,
    }
    
    // Store in database
    _, err := al.db.Exec(`
        INSERT INTO audit_log (timestamp, operation, key_ref, success)
        VALUES (?, ?, ?, ?)
    `, entry.Timestamp, entry.Operation, entry.KeyRef, entry.Success)
    
    return err
}

// Example log output:
// [2026-02-16T10:30:00Z] Tool: web_search, Key: {{brave_key}}, Success: true
// Notice: Actual API key never appears in logs
```

---

## 5. Layer 1: Encrypted Storage

### 5.1 OS Keyring Integration

**Recommendation:** Use platform-native keyrings with fallbacks.

```go
package security

import (
    "fmt"
    "runtime"
    
    "github.com/zalando/go-keyring"
)

// SecureKeyStorage handles API key storage
type SecureKeyStorage struct {
    serviceName string
}

func NewSecureKeyStorage() *SecureKeyStorage {
    return &SecureKeyStorage{
        serviceName: "nanofolks.ai",
    }
}

// Store saves key to OS keyring
func (s *SecureKeyStorage) Store(provider, key string) error {
    return keyring.Set(s.serviceName, provider, key)
}

// Retrieve gets key from OS keyring
func (s *SecureKeyStorage) Retrieve(provider string) (string, error) {
    return keyring.Get(s.serviceName, provider)
}

// Delete removes key from OS keyring
func (s *SecureKeyStorage) Delete(provider string) error {
    return keyring.Delete(s.serviceName, provider)
}

// IsAvailable checks if keyring is accessible
func (s *SecureKeyStorage) IsAvailable() bool {
    // Test with dummy value
    testKey := "nanofolks-test-key"
    err := keyring.Set(s.serviceName, "test", "test")
    if err != nil {
        return false
    }
    keyring.Delete(s.serviceName, "test")
    return true
}
```

**Fallback for headless/server mode:**

```go
// FileBasedKeyStorage for servers without GUI keyring
type FileBasedKeyStorage struct {
    masterKey []byte  // Derived from user password
    dataDir   string
}

func (s *FileBasedKeyStorage) Store(provider, key string) error {
    // Encrypt with AES-GCM using master key
    encrypted, err := encrypt([]byte(key), s.masterKey)
    if err != nil {
        return err
    }
    
    // Store in restricted file (600 permissions)
    path := filepath.Join(s.dataDir, ".keys", provider+".enc")
    return os.WriteFile(path, encrypted, 0600)
}
```

### 5.2 Master Key Derivation

```go
// DeriveMasterKey creates encryption key from user password
func DeriveMasterKey(password string, salt []byte) []byte {
    // Argon2id - memory-hard, resistant to GPU cracking
    return argon2.IDKey(
        []byte(password),
        salt,
        3,          // iterations
        64*1024,    // 64MB memory
        4,          // parallelism
        32,         // 32 byte key
    )
}
```

**Library:** `golang.org/x/crypto/argon2`

---

## 6. Layer 2: Memory Protection

### 6.1 Secure Memory Allocation

```go
package security

import (
    "runtime"
    "unsafe"
    
    "golang.org/x/sys/unix"
)

// SecureString holds sensitive data in protected memory
type SecureString struct {
    data []byte
}

// NewSecureString creates protected memory for sensitive data
func NewSecureString(s string) *SecureString {
    data := make([]byte, len(s))
    copy(data, s)
    
    // Lock memory to prevent swapping
    unix.Mlock(unsafe.Pointer(&data[0]), uintptr(len(data)))
    
    return &SecureString{data: data}
}

// String returns the string (use sparingly!)
func (ss *SecureString) String() string {
    return string(ss.data)
}

// Bytes returns byte slice (prefer this over String)
func (ss *SecureString) Bytes() []byte {
    return ss.data
}

// Wipe zeros memory and unlocks
func (ss *SecureString) Wipe() {
    // Overwrite with zeros
    for i := range ss.data {
        ss.data[i] = 0
    }
    
    // Unlock memory
    unix.Munlock(unsafe.Pointer(&ss.data[0]), uintptr(len(ss.data)))
    
    // Force GC
    ss.data = nil
    runtime.GC()
}

// Destructor
func (ss *SecureString) Destroy() {
    ss.Wipe()
}
```

**Important:** Always use `defer` to ensure cleanup:

```go
apiKey := security.NewSecureString(key)
defer apiKey.Destroy()

// Use apiKey.Bytes() when calling APIs
```

### 6.2 Memory Sanitization

```go
// SecureProvider wraps an LLM provider with protected keys
type SecureProvider struct {
    providerType string
    apiKey       *SecureString
    client       *http.Client
}

// DoRequest makes API call without exposing key in logs
func (sp *SecureProvider) DoRequest(ctx context.Context, req *http.Request) (*http.Response, error) {
    // Set authorization header securely
    req.Header.Set("Authorization", "Bearer "+sp.apiKey.String())
    
    // Execute request
    resp, err := sp.client.Do(req)
    
    // Header is automatically cleared after request
    req.Header.Del("Authorization")
    
    return resp, err
}
```

---

## 7. Layer 3: Process Isolation

### 7.1 Separate Key Service (Microservice Pattern)

```go
// key_service.go - Runs as separate process
package main

import (
    "net"
    "net/rpc"
    "os"
)

// KeyService handles key operations in isolated process
type KeyService struct {
    keys map[string]*SecureString
}

func (ks *KeyService) GetKey(args *KeyRequest, reply *KeyResponse) error {
    // Validate request comes from authorized process
    if !ks.isAuthorized(args.Token) {
        return fmt.Errorf("unauthorized")
    }
    
    key, exists := ks.keys[args.Provider]
    if !exists {
        return fmt.Errorf("key not found")
    }
    
    // Return key securely
    reply.Key = key.Bytes()
    return nil
}

func main() {
    // Drop privileges
    dropPrivileges()
    
    // Restrict file system access
    restrictFilesystem()
    
    // Start RPC server on Unix socket
    listener, _ := net.Listen("unix", "/var/run/nanofolks-keys.sock")
    rpc.Register(&KeyService{})
    rpc.Accept(listener)
}
```

**Benefits:**
- Keys live in separate process address space
- If main process is compromised, keys are isolated
- Can use seccomp, AppArmor, or SELinux for hardening

### 7.2 IPC Communication

```go
// SecureIPC handles communication with key service
type SecureIPC struct {
    client *rpc.Client
    token  string  // Process authentication token
}

func (ipc *SecureIPC) GetAPIKey(provider string) (*SecureString, error) {
    req := KeyRequest{Provider: provider, Token: ipc.token}
    var resp KeyResponse
    
    err := ipc.client.Call("KeyService.GetKey", &req, &resp)
    if err != nil {
        return nil, err
    }
    
    return NewSecureString(string(resp.Key)), nil
}
```

---

## 8. Layer 4: Deterministic Access Control

### 8.1 Usage Policies

```go
// KeyUsagePolicy defines when/how keys can be used
type KeyUsagePolicy struct {
    MaxRequestsPerMinute int
    MaxRequestsPerHour   int
    AllowedEndpoints     []string
    AllowedOperations    []string
    RequireConfirmation  bool
    AuditAllUsage        bool
}

// DefaultPolicies for different providers
var DefaultPolicies = map[string]*KeyUsagePolicy{
    "openrouter": {
        MaxRequestsPerMinute: 60,
        MaxRequestsPerHour:   1000,
        AllowedEndpoints: []string{
            "api.openrouter.ai/v1/chat/completions",
        },
        AllowedOperations:   []string{"chat.completion"},
        RequireConfirmation: false,
        AuditAllUsage:       true,
    },
    "anthropic": {
        MaxRequestsPerMinute: 30,
        MaxRequestsPerHour:   500,
        AllowedEndpoints: []string{
            "api.anthropic.com/v1/messages",
        },
        AuditAllUsage: true,
    },
}
```

### 8.2 Rate Limiter

```go
// SecureRateLimiter enforces usage policies
type SecureRateLimiter struct {
    policies   map[string]*KeyUsagePolicy
    usage      map[string]*UsageStats
    mu         sync.RWMutex
}

type UsageStats struct {
    RequestsThisMinute int
    RequestsThisHour   int
    LastRequest        time.Time
}

func (rl *SecureRateLimiter) AllowRequest(provider string) error {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    policy := rl.policies[provider]
    stats := rl.usage[provider]
    
    now := time.Now()
    
    // Reset counters if time window passed
    if now.Sub(stats.LastRequest) > time.Minute {
        stats.RequestsThisMinute = 0
    }
    if now.Sub(stats.LastRequest) > time.Hour {
        stats.RequestsThisHour = 0
    }
    
    // Check limits
    if stats.RequestsThisMinute >= policy.MaxRequestsPerMinute {
        return fmt.Errorf("rate limit exceeded: max %d requests/minute", 
            policy.MaxRequestsPerMinute)
    }
    
    // Update stats
    stats.RequestsThisMinute++
    stats.RequestsThisHour++
    stats.LastRequest = now
    
    return nil
}
```

### 8.3 Endpoint Validation

```go
// ValidateEndpoint ensures request goes to allowed URL
func (rl *SecureRateLimiter) ValidateEndpoint(provider, url string) error {
    policy := rl.policies[provider]
    
    allowed := false
    for _, endpoint := range policy.AllowedEndpoints {
        if strings.Contains(url, endpoint) {
            allowed = true
            break
        }
    }
    
    if !allowed {
        return fmt.Errorf("endpoint %s not in allowed list for provider %s", 
            url, provider)
    }
    
    return nil
}
```

---

## 9. Layer 5: Audit Logging

### 9.1 Immutable Audit Trail

```go
// AuditLogger tracks all key usage
type AuditLogger struct {
    db     *sql.DB
    signer *Signer  // For tamper-proof logs
}

type AuditEntry struct {
    Timestamp   time.Time
    Provider    string
    Operation   string
    Endpoint    string
    RequestSize int
    Success     bool
    Error       string
    Hash        string  // Chain of custody
}

func (al *AuditLogger) Log(entry *AuditEntry) error {
    // Calculate hash of previous entry + current entry
    entry.Hash = al.calculateChainHash(entry)
    
    // Sign entry
    signature := al.signer.Sign(entry.Hash)
    
    // Store in append-only log
    _, err := al.db.Exec(`
        INSERT INTO audit_log 
        (timestamp, provider, operation, endpoint, request_size, success, error, hash, signature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `, entry.Timestamp, entry.Provider, entry.Operation, entry.Endpoint,
       entry.RequestSize, entry.Success, entry.Error, entry.Hash, signature)
    
    return err
}
```

### 9.2 Real-Time Monitoring

```go
// SuspiciousActivityDetector monitors for abuse
type SuspiciousActivityDetector struct {
    logger    *AuditLogger
    threshold int
}

func (sd *SuspiciousActivityDetector) Analyze() {
    // Check for:
    // - Rapid-fire requests (possible exfiltration)
    // - Requests to unusual endpoints
    // - Large request sizes (possible data theft)
    // - Requests outside normal hours
    
    suspicious := sd.detectAnomalies()
    
    for _, activity := range suspicious {
        log.Printf("ALERT: Suspicious activity detected: %+v", activity)
        
        // Optionally block key temporarily
        sd.blockKey(activity.Provider, time.Minute*5)
    }
}
```

---

## 10. Layer 6: Context Sanitization (Defense in Depth)

### 10.1 Automatic Secret Masking

```go
// Sanitizer removes secrets from all output
type Sanitizer struct {
    patterns []*regexp.Regexp
}

func NewSanitizer() *Sanitizer {
    return &Sanitizer{
        patterns: []*regexp.Regexp{
            // OpenRouter
            regexp.MustCompile(`sk-or-v1-[a-zA-Z0-9]{20,}`),
            // Anthropic
            regexp.MustCompile(`sk-ant-[a-zA-Z0-9]{20,}`),
            // OpenAI
            regexp.MustCompile(`sk-[a-zA-Z0-9]{20,}`),
            // Bearer tokens
            regexp.MustCompile(`Bearer\s+[a-zA-Z0-9\-_]+`),
            // API keys in URLs
            regexp.MustCompile(`api[_-]?key[=:]\s*[a-zA-Z0-9]+`),
        },
    }
}

func (s *Sanitizer) Sanitize(text string) string {
    result := text
    for _, pattern := range s.patterns {
        result = pattern.ReplaceAllString(result, "***REDACTED***")
    }
    return result
}
```

### 10.2 Context Builder Security

```go
// SecureContextBuilder builds context without exposing keys
type SecureContextBuilder struct {
    sanitizer *Sanitizer
}

func (scb *SecureContextBuilder) BuildContext(messages []Message) string {
    context := scb.buildFromMessages(messages)
    
    // Sanitize before returning
    return scb.sanitizer.Sanitize(context)
}

func (scb *SecureContextBuilder) buildFromMessages(messages []Message) string {
    var parts []string
    
    for _, msg := range messages {
        // Never include system messages with API keys
        if msg.Type == "system" && containsKey(msg.Content) {
            continue
        }
        
        parts = append(parts, msg.Content)
    }
    
    return strings.Join(parts, "\n")
}
```

---

## 11. Recommended Libraries

| Purpose | Library | Notes |
|---------|---------|-------|
| **OS Keyring** | `github.com/zalando/go-keyring` | Cross-platform, native integration |
| **Encryption** | `golang.org/x/crypto/argon2` | Password hashing |
| **Encryption** | `crypto/aes` + `crypto/cipher` | AES-GCM for data at rest |
| **Memory Lock** | `golang.org/x/sys/unix` | mlock/munlock system calls |
| **Secrets Management** | `gocloud.dev/secrets` | Cloud KMS abstraction |
| **Secrets Management** | `github.com/hashicorp/vault-client-go` | Enterprise-grade vault |
| **Confidential Computing** | `github.com/edgelesssys/ego` | Intel SGX enclaves |
| **Secure Memory** | `github.com/awnumar/memguard` | Protected buffers (optional) |
| **Audit Logging** | Built-in + `github.com/sigstore/rekor` | Tamper-proof logs |

---

## 12. Implementation Roadmap

### Phase 1: Basic Protection (Week 1)
- [ ] OS keyring integration
- [ ] Secure memory allocation
- [ ] Sanitizer for logs/UI
- [ ] Remove keys from config files

### Phase 2: Access Control (Week 2)
- [ ] Rate limiting per provider
- [ ] Endpoint validation
- [ ] Usage policies
- [ ] Audit logging

### Phase 3: Advanced Isolation (Week 3-4)
- [ ] Separate key service process
- [ ] IPC communication
- [ ] Process sandboxing (seccomp)
- [ ] Anomaly detection

### Phase 4: Enterprise Features (Future)
- [ ] HashiCorp Vault integration
- [ ] HSM support (YubiKey, TPM)
- [ ] Remote attestation (EGo)
- [ ] Multi-factor authentication

---

## 13. Configuration Example

```json
{
  "security": {
    "keyStorage": {
      "type": "keyring",
      "fallback": "file",
      "fileEncryption": "aes-gcm-256"
    },
    "memoryProtection": {
      "lockMemory": true,
      "autoWipe": true,
      "wipeInterval": 300
    },
    "symbolicKeys": {
      "enabled": true,
      "exposeToLLM": true
    },
    "rateLimiting": {
      "enabled": true,
      "defaultPolicy": "standard"
    },
    "audit": {
      "enabled": true,
      "logFile": "~/.nanofolks/audit.log",
      "retentionDays": 90,
      "logKeyReferencesOnly": true
    },
    "isolation": {
      "separateKeyProcess": false,
      "sandboxLevel": "basic"
    }
  }
}
```

---

## 14. Best Practices

### For Developers

1. **Use symbolic key references** — Never expose actual keys to LLM context
2. **Never log API keys** — Use references only: "Used key: {{openrouter_key}}"
3. **Use SecureString** — For all sensitive data in memory
4. **Defer Destroy()** — Always cleanup sensitive memory after use
5. **Validate endpoints** — Before making API calls
6. **Audit everything** — Log all key usage with references

### For Users

1. **Use OS keyring** — Don't store keys in plain text files
2. **Set strong master password** — For file-based storage
3. **Enable rate limiting** — Prevent accidental abuse
4. **Review audit logs** — Regularly check for anomalies
5. **Keep software updated** — Security patches

---

## 15. Summary

This multi-layer security architecture ensures:

✅ **Keys never exposed to LLMs** — Symbolic references only (`{{openrouter_key}}`)  
✅ **Late resolution** — Keys resolved only at execution time  
✅ **Deterministic usage** — Rate limits and endpoint validation  
✅ **Memory protection** — Locked pages and secure cleanup  
✅ **Audit trail** — References only, never actual keys  
✅ **Defense in depth** — Multiple security layers  

**Core Innovation: Symbolic Key References**

Unlike traditional approaches that sanitize keys after exposure, Nanofolks Go ensures keys are **never exposed in the first place**. The LLM only sees symbolic names like `{{openrouter_key}}`, and the actual values are resolved at the last possible moment during tool execution.

**Recommended Implementation Priority:**

1. **Symbolic KeyVault** — Core innovation (highest impact)
2. **OS keyring integration** — Secure storage
3. **Secure memory allocation** — Memory protection
4. **Audit logging with references** — Usage tracking

This provides 90% of the security benefits with the symbolic reference system alone.

---

**Document Status:** Ready for Implementation  
**Priority:** High — Security foundation for entire application
