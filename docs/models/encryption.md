# Attribute encryption

Declare encrypted string/text attributes on any model. Application code continues
using plaintext for assignment, validation, forms, rendering, and serialization;
the database stores authenticated ciphertext. Rich-text bodies use the same
service when declared with `encrypted=True`.

## Setup

Generate dedicated keys and copy the printed YAML into encrypted credentials:

```sh
bin/flask db:encryption:init
bin/flask credentials:edit
```

```yaml
encryption:
  primary_key: <base64-encoded 32-byte key>
  deterministic_key: <another base64-encoded 32-byte key>
```

The command prints new secrets without changing existing credentials. Do not log
or commit its plaintext output. Neither the credentials master key nor the Flask
signing secret is reused for attribute encryption.

Keys can instead come from `FLASKTEROIDS_ENCRYPTION_PRIMARY_KEY` and
`FLASKTEROIDS_ENCRYPTION_DETERMINISTIC_KEY`, or from
`config.encryption.primary_key` and `config.encryption.deterministic_key`.
Explicit configuration takes precedence over the environment, which takes
precedence over credentials.
Python callers can generate keys with
`flaskteroids.encryption.generate_encryption_key()`.

The primary key serves randomized encryption, including ordinary `encrypts(...)`
declarations and encrypted rich-text bodies. The deterministic key serves only
encryption explicitly requested with `deterministic=True`. Neither is a database
primary key.

Configure separate keys for each application/environment, including tests.
Keep keys outside database backups, and retain keys needed to restore old backups.

## Direct use outside models

The same service encrypts UTF-8 strings in other application code, using the same
configuration and keys:

```python
from config.environment import application
from flaskteroids.encryption import decrypt, encrypt

with application.app_context():
    ciphertext = encrypt("Sensitive value", context="external_service.token")
    plaintext = decrypt(ciphertext, context="external_service.token")
```

Use a stable, purpose-specific context; decryption requires the same context.
Both calls default to randomized encryption with the primary key. Pass
`deterministic=True` to both calls to use the deterministic key instead.
Requests and jobs already run inside an application context.

## Declare attributes

Create ordinary columns through migrations, preferably `text`:

```sh
bin/flask generate model Customer name:string email:text notes:text
bin/flask db:migrate
```

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import encrypts, validates


class Customer(ApplicationModel):
    encrypts("email", deterministic=True, downcase=True)
    encrypts("notes")

    validates("name", presence=True)
    validates("email", presence=True)
```

```python
customer = Customer.create(
    name="Ada",
    email="Ada@EXAMPLE.COM",
    notes="Private notes",
)
customer.email                         # "ada@example.com"
customer.notes                         # "Private notes"
customer.update(notes="Revised notes")
customer.reload().notes                 # "Revised notes"
Customer.encrypted_attributes()         # frozenset({"email", "notes"})
customer.ciphertext_for("notes")        # Authenticated ciphertext
```

`encrypts` accepts multiple names with the same options and can be inherited from
abstract application bases and concerns. `downcase=True` normalizes assignment
and query input using lowercase; it does not retain the original casing.

### Storage requirements

Encryption adds overhead and base64 expansion, so prefer `text` to `string(255)`.
Limited string columns are supported, but a ciphertext that exceeds the declared
size raises `EncryptionError`, without including the plaintext in the exception.
Use normal model length validations for application-facing limits.

Encrypted attributes must have real string/text columns. Primary keys, foreign
keys, and plaintext server defaults are rejected. Set application defaults with
normal assignment or initialization callbacks instead of database defaults.
Unique indexes/constraints require deterministic encryption. No companion
ciphertext column or application-managed SQLAlchemy mapping is needed. Encrypted
tables require a single model class per application registry; mapping a second
model class to the same table is rejected rather than sharing encryption types
implicitly between declarations.

`None` is stored as SQL NULL. Empty strings are encrypted, not converted to NULL.

## Queries

Randomized encryption is the default: identical values produce different
ciphertexts. Opt into deterministic encryption only for fields needing equality
lookups or unique indexes:

```python
Customer.find_by(email="ADA@example.com")
Customer.where(email="ada@example.com")
Customer.where(Customer.email.in_(["ada@example.com", "grace@example.com"]))
Customer.where(notes=None)
```

Deterministic fields support equality, inequality, `IN`, and `NOT IN`; encrypted
fields support NULL checks. Other comparisons, substring searches, and framework
ordering raise `EncryptionError`. Encryption does not preserve plaintext sort
order. Deterministic encryption leaks equality and frequency information.

Native mapped SQLAlchemy selects, inserts, and updates use the same encrypted
types. Raw SQL and explicit type coercion bypass them and are advanced escape
hatches, not ordinary application workflows. Raw SQL filters are not rewritten,
and ordering/grouping encrypted columns through native SQL does not acquire
plaintext semantics. Do not use raw writes for encrypted values.

## Forms, validation, inspection, and fixtures

Ordinary form helpers receive plaintext. Failed validation retains submitted
values for redisplay; successful saves track plaintext attribute changes.
Encrypted fields are omitted from model `repr`, so inspecting a model does not
expose their values. SQL parameters passing through mapped encrypted types contain
ciphertext, not plaintext.

JSON serialization and rendered responses still contain plaintext. Encryption is
not an authorization boundary; authorize those responses and configure
`_serialization_exclude` or explicit serializers where necessary. Do not log
plaintext request bodies, model changes, form data, or serialized responses.

YAML fixtures use ordinary plaintext values. The fixture loader automatically
encrypts declared attributes; test applications must configure dedicated test
keys. No `encrypt_fixtures` switch is required.

## Rotation and existing data

For randomized encryption, configure primary keys oldest to newest:

```python
config.encryption.primary_key = [previous_key, current_key]
```

The last key encrypts new writes; every listed key may decrypt. Re-encrypt records
before retiring an old key:

```python
for customer in Customer.all():
    customer.encrypt()
```

`encrypt()` updates declared encrypted attributes without saving unrelated pending
attributes or running save callbacks/validations. It joins model transactions and
requires a persisted record. Normal saves handle new records.

The deterministic key is a single stable key: changing it breaks existing equality
queries and unique-index semantics. Online deterministic-key rotation and queries
across multiple encryption schemes are not implemented. Such a change needs a
planned data/index migration, not simply replacing the configured key.

Plaintext in an encrypted column is rejected by default. To explicitly migrate
existing plaintext, back up data, stop normal traffic/workers, temporarily set:

```python
config.encryption.support_unencrypted_data = True
```

Then load records and call `encrypt()`, verify the data, and remove that setting
before resuming traffic. This option permits plaintext reads but does not disable
encryption of writes. Wrong keys, failed authentication, malformed envelopes, and
unsupported envelope versions still raise `EncryptionError`.

For rich-text bodies, use the same keys and rotate with:

```python
for post in Post.with_rich_text_content():
    post.content.encrypt()
```

The rich-text record also supports explicit plaintext migration through its
`encrypt()` method without the temporary plaintext-read setting. See
[Rich text](../other/rich_text.md#encryption).

## Security and limitations

Randomized encryption uses AES-256-GCM with a fresh 96-bit nonce. Deterministic
encryption uses AES-256-SIV with a domain-separated, HKDF-derived key. Both
authenticate an attribute context, so moving ciphertext to another model/attribute
fails authentication. Model and attribute names are part of that context: renaming
one requires decrypting/re-encrypting its data under the new context, not just
renaming a declaration. Deterministic encryption uses the audited SIV primitive
provided by the cryptography library.

Keys are base64-encoded raw 32-byte keys. Ciphertext uses Flaskteroids-specific
envelopes, and model reads decrypt through mapped database types.

Custom key providers, case-insensitive encryption that preserves original casing,
serialized/non-string attributes, a plaintext-writing model `decrypt()` operation,
and online multi-scheme deterministic queries are not implemented.

Encryption protects database contents, not an application holding its keys.
Ciphertext can still reveal length, NULL values, and deterministic equality.
It does not encrypt uploaded file bytes, attachment metadata, rendered HTML,
JSON responses, process memory, or secrets logged by application code. Use storage
provider encryption and download authorization for files. Passwords should use
`has_secure_password`, not reversible encryption.
