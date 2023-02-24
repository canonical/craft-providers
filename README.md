# Craft Providers

This project aims to provide Python interfaces for instantiating and executing
builds for a variety of target environments.

Initial providers include:
- LXD containers
- Multipass VMs

Host support is targeted for:
- Linux
- Mac OS X
- Windows


# License

Free software: GNU Lesser General Public License v3


# Documentation

https://canonical-craft-providers.readthedocs-hosted.com/en/latest/

# Contributing

A `Makefile` is provided for easy interaction with the project. To see
all available options run:

```
make help
```

## Running tests

To run all tests in the suite run:

```
make tests
```

## Adding new requirements

If a new dependency is added to the project run:

```
make freeze-requirements
```

## Verifying documentation changes

To locally verify documentation changes run:

```
make docs
```

After running, newly generated documentation shall be available at
`./docs/_build/html/`.


## Committing code

Please follow these guidelines when committing code for this project:

- Use a topic with a colon to start the subject
- Separate subject from body with a blank line
- Limit the subject line to 50 characters
- Do not capitalize the subject line
- Do not end the subject line with a period
- Use the imperative mood in the subject line
- Wrap the body at 72 characters
- Use the body to explain what and why (instead of how)
