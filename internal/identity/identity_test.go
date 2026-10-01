package identity

import (
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestSecCHUAMatchesRealChromeValues(t *testing.T) {
	cases := map[int]string{
		// Observed in real Chrome 120.
		120: `"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"`,
		// Observed in Playwright's Chromium 153 (headless brand renamed).
		153: `"Google Chrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"`,
	}
	for major, want := range cases {
		if got := SecCHUA(major, "Google Chrome"); got != want {
			t.Errorf("SecCHUA(%d) = %s, want %s", major, got, want)
		}
	}
}

func TestDefaultIdentityIsConsistent(t *testing.T) {
	for _, goos := range []string{"windows", "darwin", "linux"} {
		id := Default(goos)
		family, major := id.Browser()
		if family != "chrome" || major != DefaultChromeMajor {
			t.Errorf("%s: browser = %s %d", goos, family, major)
		}
		if !strings.Contains(id.SecCHUA, `"Chromium";v="152"`) || !strings.Contains(id.UserAgent, "Chrome/152.0.0.0") {
			t.Errorf("%s: version mismatch between %q and %q", goos, id.UserAgent, id.SecCHUA)
		}
	}
	if Default("windows").SecCHUAPlatform != `"Windows"` || !strings.Contains(Default("windows").UserAgent, "Windows NT 10.0") {
		t.Error("windows identity does not match its platform")
	}
	if Default("darwin").SecCHUAPlatform != `"macOS"` {
		t.Error("darwin identity does not match its platform")
	}
}

func TestBrowserDetection(t *testing.T) {
	cases := []struct {
		ua     string
		family string
		major  int
	}{
		{"Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0", "firefox", 140},
		{"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0", "chrome", 150},
		{"curl/8.0", "chrome", DefaultChromeMajor},
	}
	for _, c := range cases {
		family, major := Identity{UserAgent: c.ua}.Browser()
		if family != c.family || major != c.major {
			t.Errorf("%q: got %s %d", c.ua, family, major)
		}
	}
}

func TestSaveLoadReset(t *testing.T) {
	path := filepath.Join(t.TempDir(), "identity.json")

	id, err := Load(path)
	if err != nil || id.Source != "default" || id.UserAgent != Default(runtime.GOOS).UserAgent {
		t.Fatalf("missing file should give the default identity: %+v %v", id, err)
	}

	custom := Default("windows")
	custom.Source = "har"
	custom.LiTrack = `{"clientVersion":"1.0"}`
	custom.HeaderOrder = []string{"user-agent", "accept"}
	if err := Save(path, custom); err != nil {
		t.Fatal(err)
	}
	loaded, err := Load(path)
	if err != nil || loaded.Source != "har" || loaded.LiTrack != custom.LiTrack || len(loaded.HeaderOrder) != 2 {
		t.Fatalf("unexpected identity %+v %v", loaded, err)
	}

	if err := Reset(path); err != nil {
		t.Fatal(err)
	}
	if err := Reset(path); err != nil {
		t.Fatal("resetting twice should not fail")
	}
	if loaded, _ := Load(path); loaded.Source != "default" {
		t.Error("reset did not restore the default identity")
	}
}
