// Package errs defines the error kinds that the CLI reports as clean messages.
package errs

import "fmt"

// Kind classifies an error so the CLI can pick an exit code and wording.
type Kind int

const (
	// Usage means the command was called with invalid input.
	Usage Kind = iota + 1
	// AuthRequired means there is no valid LinkedIn session.
	AuthRequired
	// Challenge means LinkedIn asked for a security check.
	Challenge
	// RateLimited means LinkedIn rejected a request for being too frequent.
	RateLimited
	// Budget means sending another request would exceed a request budget.
	Budget
	// Cooldown means requests are paused after LinkedIn pushed back.
	Cooldown
	// API means LinkedIn's internal API returned something unexpected.
	API
	// Validation means a post or other input failed a content check.
	Validation
	// Storage means local state (session, keyring, files) could not be used.
	Storage
)

// Error is an error with a Kind.
type Error struct {
	Kind    Kind
	Message string
	Err     error
}

func (e *Error) Error() string {
	if e.Err != nil && e.Message == "" {
		return e.Err.Error()
	}
	return e.Message
}

func (e *Error) Unwrap() error { return e.Err }

// New creates an Error of the given kind.
func New(kind Kind, format string, args ...any) *Error {
	return &Error{Kind: kind, Message: fmt.Sprintf(format, args...)}
}

// Wrap creates an Error of the given kind that wraps err.
func Wrap(kind Kind, err error, format string, args ...any) *Error {
	return &Error{Kind: kind, Message: fmt.Sprintf(format, args...), Err: err}
}

// HTTPError is returned for unexpected HTTP statuses from LinkedIn.
type HTTPError struct {
	Status  int
	URL     string
	Snippet string
}

func (e *HTTPError) Error() string {
	return fmt.Sprintf("LinkedIn API returned HTTP %d for %s: %s", e.Status, e.URL, e.Snippet)
}
