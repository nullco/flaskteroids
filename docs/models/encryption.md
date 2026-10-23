# Attribute encryption

Use attribute encryption to keep sensitive strings out of your database in
plaintext. Your application still reads and assigns normal strings; Flaskteroids
encrypts database writes and decrypts reads automatically.

This is different from [encrypted credentials](../configuration.md#encrypted-credentials):
credentials protect application secrets in a file, while attribute encryption
protects model data in database columns. The two features use separate keys.

## Setup

From your application directory, generate keys and open the credentials editor:

```sh
bin/flask db:encryption:init
bin/flask credentials:edit
```

The first command only prints new keys. Copy its YAML into the editor:

```yaml
encryption:
  primary_key: <generated primary key>
  deterministic_key: <generated deterministic key>
```

- `primary_key` encrypts ordinary attributes and encrypted rich-text bodies.
- `deterministic_key` encrypts attributes declared with `deterministic=True`,
  which support equality lookups.

Neither key is a database primary key. Neither the credentials master key nor
Flask's signing secret is reused for attribute encryption.

**Do not commit or log the printed keys.** Store them in encrypted credentials or
supply them through your deployment's secret management. Use separate keys for
each application and environment, including tests. Keep keys separate from
database backups, and retain the keys needed to restore older backups.

### Other ways to supply keys

You can use environment variables instead of credentials:

```text
FLASKTEROIDS_ENCRYPTION_PRIMARY_KEY
FLASKTEROIDS_ENCRYPTION_DETERMINISTIC_KEY
```

Or set `config.encryption.primary_key` and
`config.encryption.deterministic_key` in application configuration.
The lookup order is **explicit configuration → environment → credentials**.

Keys are base64-encoded 32-byte values, not passwords. Python code can generate
one with `flaskteroids.encryption.generate_encryption_key()`.

## Declare attributes

Create ordinary string or text columns through migrations. Prefer `text` because
encryption increases the stored size:

```sh
bin/flask generate model Customer name:string email:text notes:text
bin/flask db:migrate
```

Add the declarations to `app/models/customer.py`:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import encrypts, validates


class Customer(ApplicationModel):
    encrypts("notes")
    encrypts("email", deterministic=True, downcase=True)

    validates("name", presence=True)
    validates("email", presence=True)
```

Use the model normally:

```python
customer = Customer.create(
    name="Ada",
    email="Ada@EXAMPLE.COM",
    notes="Private notes",
)
customer.email                          # "ada@example.com"
customer.notes                          # "Private notes"
customer.update(notes="Revised notes")
customer.reload().notes                 # "Revised notes"
Customer.encrypted_attributes()          # frozenset({"email", "notes"})
customer.ciphertext_for("notes")         # Ciphertext rather than plaintext
```

`encrypts` accepts several names with the same options, and declarations can be
inherited from abstract model bases and concerns. `downcase=True` lowercases
assignment and query input; **it does not preserve original casing**.

If the columns already contain plaintext, follow
[the migration steps below](#rotation-and-existing-data) before serving traffic.
Adding a declaration alone does not convert existing rows.

### Storage requirements

- Use real string/text columns. Primary keys and foreign keys cannot be encrypted.
- Do not use plaintext database defaults on encrypted columns. Set defaults through
  application assignment or initialization callbacks instead.
- Unique indexes and constraints require `deterministic=True`.
- `None` stays SQL NULL; an empty string is encrypted.

A limited string column is allowed, but oversized ciphertext raises
`EncryptionError` without exposing plaintext in the message. Prefer `text` and
use model length validations for user-facing limits.

No companion ciphertext column or custom SQLAlchemy mapping is needed. Only one
model class per application registry may map to an encrypted table.

## Queries

Choose the mode according to how you need to use the field:

| Mode | Same value written twice | Supported lookups |
| --- | --- | --- |
| Randomized, the default | Different ciphertexts | NULL checks |
| Deterministic | Same ciphertext within the same attribute context | Equality, inequality, `IN`, `NOT IN`, and NULL checks |

Use randomized encryption unless you need equality lookups or a unique index.
Deterministic encryption reveals which values are equal and how often they occur.

```python
Customer.find_by(email="ADA@example.com")
Customer.where(email="ada@example.com")
Customer.where(Customer.email.in_(["ada@example.com", "grace@example.com"]))
Customer.where(notes=None)
```

Substring searches, range comparisons, and framework ordering raise
`EncryptionError`. Ciphertext does not preserve plaintext sort order.

Mapped SQLAlchemy selects, inserts, and updates use the same encryption types.
**Raw SQL and explicit type coercion bypass them.** Raw filters are not rewritten,
and native ordering/grouping does not gain plaintext semantics. Do not use raw
SQL writes for encrypted values.

## Forms, validation, inspection, and fixtures

Forms and validations work with plaintext. A failed validation keeps the submitted
value for redisplay, and change tracking uses plaintext values.

Encrypted attributes are omitted from model `repr`. SQL parameters that pass
through mapped encrypted types contain ciphertext. These protections do not
cover logs of request bodies, form values, or model changes.

**Rendered HTML and JSON serialization still contain plaintext.** Authorize access
to those responses. Use `_serialization_exclude` or explicit serializers to omit
sensitive fields where needed; encryption does not make them safe to expose.

YAML fixtures use ordinary plaintext values. The fixture loader encrypts declared
attributes automatically. Configure dedicated test keys; no `encrypt_fixtures`
switch is needed.

## Direct use outside models

Use the same service for UTF-8 strings that are not model attributes:

```python
from config.environment import application
from flaskteroids.encryption import decrypt, encrypt

with application.app_context():
    ciphertext = encrypt("Sensitive value", context="external_service.token")
    plaintext = decrypt(ciphertext, context="external_service.token")
```

Choose a stable, purpose-specific `context`. Decryption requires the same context.
Both calls default to randomized encryption with the primary key. To use the
deterministic key, pass `deterministic=True` to both calls.
Requests and jobs already have an application context.

## Rotation and existing data

### Rotate the primary key

Configure randomized-encryption keys from oldest to newest:

```python
config.encryption.primary_key = [previous_key, current_key]
```

The last key encrypts new writes; all listed keys may decrypt. Inside an
application context, re-encrypt existing records before removing an old key:

```python
for customer in Customer.all():
    customer.encrypt()
```

`encrypt()` requires a saved record. It updates encrypted attributes without
saving unrelated pending attributes or running save callbacks and validations.
It participates in model transactions. New records use normal saves.

### Keep the deterministic key stable

The deterministic key must be a single key, not a list. Changing it breaks
existing equality queries and unique-index behavior. Online rotation and queries
across multiple encryption schemes are not supported. Plan a data/index migration
instead of simply replacing this key.

### Convert existing plaintext

Plaintext in an encrypted column is rejected by default. To migrate it:

1. Back up the data and stop normal traffic and workers.
2. Temporarily allow plaintext reads:

   ```python
   config.encryption.support_unencrypted_data = True
   ```

3. Load records and call `record.encrypt()` inside an application context.
4. Verify the data, remove the setting, and only then resume traffic.

This setting permits plaintext reads; writes remain encrypted. Wrong keys,
modified ciphertext, malformed envelopes, and unsupported envelope versions
still raise `EncryptionError`.

### Re-encrypt rich text

Rich text uses the same primary keys, but has its own operation:

```python
for post in Post.with_rich_text_content():
    post.content.encrypt()
```

This also converts existing plaintext bodies without enabling plaintext reads.
See [Rich text](../other/rich_text.md#encryption).

## Security and limitations

Randomized encryption uses AES-256-GCM with a fresh 96-bit nonce. Deterministic
encryption uses the `cryptography` library's AES-256-SIV primitive with a
domain-separated, HKDF-derived key.

Both modes authenticate the model/attribute context. Moving ciphertext to another
attribute fails authentication. **Renaming a model or encrypted attribute requires
decrypting and re-encrypting its data under the new context**, not just renaming
the declaration. Stored values use Flaskteroids-specific versioned envelopes.

Encryption protects database contents, not a running application holding its keys.
It can still reveal value lengths, NULLs, and deterministic equality. It does not
protect process memory, application logs, rendered responses, uploaded file bytes,
or attachment metadata. Use storage-provider encryption and download authorization
for files. Use `has_secure_password` for passwords, not reversible encryption.

Custom key providers, encryption that ignores case while preserving original
casing, non-string/serialized attributes, a model operation that writes decrypted
plaintext, and online multi-scheme deterministic queries are not supported.
