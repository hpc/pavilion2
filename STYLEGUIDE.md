# Pavilion Style Guide

- These are not arbitrary rules, but hard-won lessons gained from years of software development.
- Each of these rules has practical implications, often in terms of readability and testibility.

## Optimize for Readability and Testability

- Cognitive load

## Maintain Separation of Concerns

- Each function, method, or object, should do one thing, and one thing only.

## Prefer Pure Functions

- Prefer pure functions for testability
- Use dependency injection to keep functions pure
- Label pure methods as static methods
- Functions that might reasonably needed by multiply entities should go in a utilities module

## Prefer Returning "degenerate" Objects Over Raising Exceptions

- Where sensible, return `None`, empty lists or sets, etc. rather than raising exceptions.
    - Maintains function purity.
- Leave it up to the caller whether to raise an exception.

## Keep Functions Short

- Lengthy functions hint at poor separation of concerns

## Keep Objects Relatively Small

- Compose smaller, simpler objects for complex behavor.
- Promotes testing and reusability.

## Avoid Deep Object Hierarchies

- Distributes logic over multiple classes
- Makes control flow harder to trace
- Prefer composition over inheritance

## Use Explicit Conditional Tests

- Reserve simple tests (e.g. `if foo:`) for actual boolean values.
- Test against other types should explicit test properties of objects rather than relying on
  implicit boolean-like behavior.
    - `if foo is None:`
    - `if len(foo) == 0:`
- Clearly telegraphs expected type and properties of object.
- Makes intent clearer and more explicit.
- Improves readability.
- More generally, using the `if foo:` idiom on certain third-party types (such as NumPy arrays)
  can result in runtime errors.
- More pedantically, you should respect objects' type; you shouldn't treat things that aren't
  booleans as booleans.

## Prefer Functional Primitives over Loops

- Prefer functional primitives (e.g. `map`, `filter`, `any`) over loops when possible, especially
  lengthy, nested, or otherwise complex loops.
- Use anonymous (`lambda`) functions for simple map targets.
- For more complex workflows, it may make sense to define a custom (pure) function and then map
  that over its targets.
    - This is cleaner than using complex `lambda` functions.
    - Also has the benefit of being easier to test.
- Functional operations are effectively stateless, reducing potential for error.
- Note that these functions return iterators, which can cause subtle bugs (e.g. can only be
  consumed once)
    - May make sense to convert to list.
        - Can't get length otherwise
- Don't nest too many at once. If you're nesting more than approximately three functional
  primitives, break the logic up.
- If you need to raise an exception with information about a particular item, it may still be
  necessary to use a for loop.
    - However, using the custom function (see above) is a good choice.
- Make use of functional utilities provided in `micro` module

## Keep __init__() methods minimal

- Do not perform expensive operations (especially I/O)
- Do bare minimum to set up expected state of object
    - State at end of __init__() method should be consistent with state expected by all other
      methods.
- Separate logic out into helper methods when necessary
    - If you have this much logic, you should probably refactory.

## Use Type Annotations for Function Signatures

- All functions and methods should have all arguments and return value type-annotated
    - `self` and `cls` arguments do not need to be annotated
    - `__init__()` return type doesn't need to be annotated
- Functions and methods that don't return anything should have return type annotated as `None`

## Function Doctrings

- All functions and methods (public and private) should have descriptive doctrings.
- Use `reStructuredText` format.
- Include behavior description; don't reference implementation.
- Description should be as concise as possible while still providing a complete description.
- Also provide notes providing significant considerations relevant to developers (e.g. thread
  safety).
- Include argument and return types.
    - Include brief (one-line) description for each.
- Also note any exceptions that may be raised.
- Objects and modules should also have their own docstrings.

## Mark Methods as Private where Appropriate

- Private methods should begin with a single underscore.

## Don't Reinvent the Wheel

- Prefer library implementations over custom solutions.
- Solutions provided in standard libraries are a no-brainer.
- Reliable, commonly used, and actively maintained third-party libraries are a good choice.
   - Don't add dependencies without discussion with other developers. 

## Prefer `argparse` over `sys.argv`

- Make arguments required or optional as appropriate.
- Arguments should have clear names that telegraph what they do
- All optional arguments should have sensible default values.
- Commonly used options should have short-form variants.
- Perform as much validation as possible at parse time
    - Perform type validation at parsing time when possible
        - Use `type` argument.
        - For instance, `type=Path` for filesystem paths
    - Perform validation on number of values.
- Every argument should have descriptive help text.
    - Concise as possible but no more than that.

## Don't Pass Large Objects Into Functions and Methods

- Especially not `argparse` `Namespace` objects.
- Makes testing more difficult.
- Instead, extract needed values from object and pass those in instead.

## Group Related Data Together

- Use data classes

## Import Statements

- Prefer direct imports, except where naming might cause collision or confusion
- Separate module imports `from`-style imports, and internal imports into different sections
