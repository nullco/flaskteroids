# Writing Flaskteroids guides

A guide helps someone understand a feature and use it in an application. It is
not an inventory of every method, option, exception, or implementation detail.

This approach takes inspiration from the
[Rails Guides](https://guides.rubyonrails.org/), especially
[Getting Started](https://guides.rubyonrails.org/getting_started.html),
[Active Record Basics](https://guides.rubyonrails.org/active_record_basics.html),
and the [Guides Guidelines](https://guides.rubyonrails.org/ruby_on_rails_guides_guidelines.html).
Borrow their teaching structure, not claims that Flaskteroids implements every
Rails feature.

## Start with the reader's goal

Open with the problem the feature solves, followed by a short list of what the
reader will learn. State prerequisites and the starting application state before
the first example.

Choose one kind of page:

- **Tutorial:** build a feature step by step in a named application. Each step
  depends on the ones before it.
- **Component guide:** explain a feature through a small, coherent example.
  Readers should not have to complete the whole store tutorial first.

Keep exhaustive signatures, option tables, backend internals, and extension
contracts for separate API documentation.

## Teach one workflow at a time

Introduce the simplest useful path first:

1. Explain what the reader is about to do and why.
2. Show the command or code, including its file path.
3. Explain the result and how to check it.
4. Add alternatives only after the basic workflow works.

Keep related steps together. A form example should lead to permitted parameters,
saving, and validation redisplay before discussing unrelated helper options.
A mailer example should reach a local preview before requiring SMTP setup.

Split a page when it starts teaching a separate feature. Link to the focused
guide instead of repeating its installation steps or configuration catalog.

## Write directly and calmly

Address the reader as “you.” Use “we” when walking through a tutorial together.
Prefer short paragraphs, active sentences, and familiar words.

Lead with application behavior:

- Prefer “Assigning a value does not save it” over “Scalar publication is staged.”
- Prefer “If saving fails, render the submitted object again” over “The input
  graph retains rejected state.”
- Explain a term such as “partial” before showing several ways to call it.

Use sentence-case headings that describe a task or concept. Avoid headings such
as “Advanced” that do not tell readers what they will find.

## Make examples usable

Use one set of domain names within a guide. Show imports at module scope, and
identify the file being edited. Say whether a snippet replaces a class, adds a
method, or changes an existing declaration.

Run application commands with `bin/flask` from the application root. Use
`flask new` before the application exists. Explain any additional tools, worker
processes, migrations, or server restarts when they become necessary.

Do not include terminal prompt characters in copyable shell commands. Use
`pycon` for interactive Python examples with prompts and results.

Keep examples focused on the step being taught. A small table can clarify a
choice; a catalog of every supported option belongs in API documentation.

## Keep important boundaries close

Do not remove a warning merely to shorten a guide. Explain safety and correctness
where the reader needs them: permitted parameters beside assignment, CSRF beside
form submission, download authorization beside file links, and after-commit
delivery beside background email.

Describe intentional limitations in terms of the reader's task. Distinguish what
works from what the application must supply. Do not imply full Rails parity from
a shared method name, or require SQLAlchemy session knowledge for ordinary work.

## Review a guide

Before publishing, check:

- Can a reader identify the goal and starting point from the introduction?
- Does each example introduce one idea and explain its result?
- Does the main workflow work without following an advanced detour?
- Are failures, security boundaries, and unsupported behavior clear?
- Do moved sections have updated links and navigation?
- Does the page end with a useful next step rather than another option list?

Build the site with `mkdocs build --strict` after editing links or navigation.
