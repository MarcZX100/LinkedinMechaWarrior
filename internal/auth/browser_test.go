package auth

import (
	"context"
	"path/filepath"
	"runtime"
	"testing"
)

// The fixture is a real Firefox cookies.sqlite, found through profiles.ini
// under a fake home directory (Linux paths).
func TestFindSessionsReadsFirefoxProfile(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("the fixture uses Linux Firefox paths")
	}
	home, err := filepath.Abs(filepath.Join("testdata", "home"))
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("HOME", home)

	candidates, err := FindSessions(context.Background(), "firefox")
	if err != nil {
		t.Fatal(err)
	}
	if len(candidates) != 1 {
		t.Fatalf("found %d sessions", len(candidates))
	}
	c := candidates[0]
	if c.Label() != "firefox (default)" {
		t.Errorf("label %q", c.Label())
	}
	want := map[string]string{"li_at": "AQEDfirefoxsession", "JSESSIONID": `"ajax:555"`, "bcookie": `"v=2&ff"`}
	for name, value := range want {
		if c.Cookies[name] != value {
			t.Errorf("%s = %q, want %q (quotes must be kept)", name, c.Cookies[name], value)
		}
	}
	if _, ok := c.Cookies["lidc"]; ok {
		t.Error("expired cookie was imported")
	}
	if _, ok := c.Cookies["other"]; ok {
		t.Error("cookie from another site was imported")
	}
	if c.Created.IsZero() {
		t.Error("session creation time not read")
	}

	if _, err := FindSessions(context.Background(), "chrome"); err == nil {
		t.Error("expected no session in chrome")
	}
}
