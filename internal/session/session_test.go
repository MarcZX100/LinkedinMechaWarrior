package session

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/zalando/go-keyring"
)

func validCookies() map[string]string {
	return map[string]string{
		"li_at":      "AQEDtoken",
		"JSESSIONID": `"ajax:123"`,
		"bcookie":    `"v=2&abc"`,
		"_ga":        "tracking-cookie-we-do-not-keep",
	}
}

func TestNewKeepsOnlyKnownCookiesAndValidates(t *testing.T) {
	s, err := New(validCookies(), "test")
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := s.Cookies["_ga"]; ok {
		t.Error("unknown cookie was kept")
	}
	if s.CSRFToken() != "ajax:123" {
		t.Errorf("csrf token = %q", s.CSRFToken())
	}
	if got := s.CookieHeader(); got != `bcookie="v=2&abc"; JSESSIONID="ajax:123"; li_at=AQEDtoken` {
		t.Errorf("cookie header = %q", got)
	}

	if _, err := New(map[string]string{"li_at": "x"}, "test"); err == nil {
		t.Error("a session without JSESSIONID should be rejected")
	}
}

func TestUpdate(t *testing.T) {
	s, _ := New(validCookies(), "test")
	if !s.Update("lidc", "b=1", false) || s.Cookies["lidc"] != "b=1" {
		t.Error("new cookie not stored")
	}
	if s.Update("lidc", "b=1", false) {
		t.Error("unchanged cookie reported as a change")
	}
	if s.Update("_ga", "x", false) {
		t.Error("unknown cookie stored")
	}
	if !s.Update("li_at", `"delete me"`, false) || s.Validate() == nil {
		t.Error("deleting li_at must invalidate the session")
	}
}

func TestFileStoreRoundTripAndPermissions(t *testing.T) {
	path := filepath.Join(t.TempDir(), "session.json")
	store := FileStore{Path: path}

	if _, err := store.Load(); !errors.Is(err, ErrNoSession) {
		t.Fatalf("expected ErrNoSession, got %v", err)
	}
	s, _ := New(validCookies(), "test")
	if _, err := store.Save(s); err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS != "windows" {
		info, _ := os.Stat(path)
		if info.Mode().Perm() != 0o600 {
			t.Errorf("session file permissions = %v", info.Mode().Perm())
		}
	}
	loaded, err := store.Load()
	if err != nil || loaded.Cookies["li_at"] != "AQEDtoken" || loaded.Source != "test" {
		t.Fatalf("unexpected session %+v %v", loaded, err)
	}
	if err := store.Delete(); err != nil {
		t.Fatal(err)
	}
	if err := store.Delete(); err != nil {
		t.Fatal("deleting twice should not fail")
	}
}

func TestAutoStorePrefersKeyringAndCleansUpTheFile(t *testing.T) {
	keyring.MockInit()
	path := filepath.Join(t.TempDir(), "session.json")
	store := AutoStore{File: FileStore{Path: path}}
	s, _ := New(validCookies(), "test")

	// A stale copy from a time without keyring.
	if _, err := store.File.Save(s); err != nil {
		t.Fatal(err)
	}
	where, err := store.Save(s)
	if err != nil || where != "the system keyring" {
		t.Fatalf("saved to %q: %v", where, err)
	}
	if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
		t.Error("stale session file was not removed")
	}
	if loaded, err := store.Load(); err != nil || loaded.Cookies["li_at"] != "AQEDtoken" {
		t.Fatalf("unexpected session %+v %v", loaded, err)
	}
	if err := store.Delete(); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Load(); !errors.Is(err, ErrNoSession) {
		t.Errorf("expected ErrNoSession after delete, got %v", err)
	}
}

func TestAutoStoreFallsBackToFile(t *testing.T) {
	keyring.MockInitWithError(errors.New("no dbus"))
	defer keyring.MockInit()
	path := filepath.Join(t.TempDir(), "session.json")
	store := AutoStore{File: FileStore{Path: path}}
	s, _ := New(validCookies(), "test")

	where, err := store.Save(s)
	if err != nil || where != path {
		t.Fatalf("saved to %q: %v", where, err)
	}
	if loaded, err := store.Load(); err != nil || loaded.Cookies["li_at"] != "AQEDtoken" {
		t.Fatalf("unexpected session %+v %v", loaded, err)
	}
}
