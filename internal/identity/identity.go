// Package identity describes which browser lmw presents itself as.
//
// Everything a server can compare must agree: the TLS and HTTP/2 fingerprint
// (chosen from the browser family and version), the User-Agent and the client
// hints. By default lmw presents itself as a current desktop Chrome on the
// local operating system. Importing a HAR file from your own browser replaces
// that with your browser's exact headers.
package identity

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"regexp"
	"runtime"
	"strconv"
	"strings"
)

// DefaultChromeMajor is the newest Chrome version with a TLS profile in tls-client.
const DefaultChromeMajor = 152

// DefaultHeaderOrder approximates the order in which Chrome sends the headers
// of a same-origin fetch(). A HAR import replaces it with the observed order.
var DefaultHeaderOrder = []string{
	"content-length",
	"sec-ch-ua-platform",
	"csrf-token",
	"x-li-lang",
	"sec-ch-ua",
	"x-li-track",
	"sec-ch-ua-mobile",
	"x-restli-protocol-version",
	"user-agent",
	"accept",
	"content-type",
	"origin",
	"sec-fetch-site",
	"sec-fetch-mode",
	"sec-fetch-dest",
	"referer",
	"accept-encoding",
	"accept-language",
	"cookie",
	"priority",
}

// Identity is the set of browser-specific request headers.
type Identity struct {
	UserAgent       string   `json:"user_agent"`
	SecCHUA         string   `json:"sec_ch_ua,omitempty"`
	SecCHUAMobile   string   `json:"sec_ch_ua_mobile,omitempty"`
	SecCHUAPlatform string   `json:"sec_ch_ua_platform,omitempty"`
	AcceptLanguage  string   `json:"accept_language"`
	LiLang          string   `json:"x_li_lang"`
	LiTrack         string   `json:"x_li_track,omitempty"`
	HeaderOrder     []string `json:"header_order,omitempty"`
	Source          string   `json:"source"`
}

// Default returns a desktop Chrome identity for the given operating system.
func Default(goos string) Identity {
	return Identity{
		UserAgent:       ChromeUserAgent(goos, DefaultChromeMajor),
		SecCHUA:         SecCHUA(DefaultChromeMajor, "Google Chrome"),
		SecCHUAMobile:   "?0",
		SecCHUAPlatform: strconv.Quote(platformName(goos)),
		AcceptLanguage:  "en-US,en;q=0.9",
		LiLang:          "en_US",
		Source:          "default",
	}
}

// ChromeUserAgent builds Chrome's reduced User-Agent string for an OS.
func ChromeUserAgent(goos string, major int) string {
	var platform string
	switch goos {
	case "windows":
		platform = "Windows NT 10.0; Win64; x64"
	case "darwin":
		platform = "Macintosh; Intel Mac OS X 10_15_7"
	default:
		platform = "X11; Linux x86_64"
	}
	return fmt.Sprintf("Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%d.0.0.0 Safari/537.36", platform, major)
}

// SecCHUA reproduces Chrome's sec-ch-ua header, including its GREASE brand.
//
// Chrome derives the fake "Not A Brand" entry and the order of the three
// brands deterministically from the major version (see Chromium's
// GetGreasedUserAgentBrandVersion), so a hand-written value is easy to spot.
func SecCHUA(major int, brand string) string {
	greaseChars := []string{" ", "(", ":", "-", ".", "/", ")", ";", "=", "?", "_"}
	greaseVersions := []string{"8", "99", "24"}
	orders := [][3]int{{0, 1, 2}, {0, 2, 1}, {1, 0, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}}

	grease := fmt.Sprintf(`"Not%sA%sBrand";v="%s"`,
		greaseChars[major%len(greaseChars)], greaseChars[(major+1)%len(greaseChars)], greaseVersions[major%len(greaseVersions)])
	chromium := fmt.Sprintf(`"Chromium";v="%d"`, major)
	branded := fmt.Sprintf(`%q;v="%d"`, brand, major)

	order := orders[major%len(orders)]
	brands := make([]string, 3)
	brands[order[0]] = grease
	brands[order[1]] = chromium
	brands[order[2]] = branded
	return strings.Join(brands, ", ")
}

var (
	chromeVersion  = regexp.MustCompile(`Chrome/(\d+)`)
	firefoxVersion = regexp.MustCompile(`Firefox/(\d+)`)
)

// Browser returns the browser family ("chrome" or "firefox") and major version
// claimed by the User-Agent. Chromium-based browsers (Edge, Brave, Opera) are "chrome".
func (i Identity) Browser() (family string, major int) {
	if m := firefoxVersion.FindStringSubmatch(i.UserAgent); m != nil {
		major, _ = strconv.Atoi(m[1])
		return "firefox", major
	}
	if m := chromeVersion.FindStringSubmatch(i.UserAgent); m != nil {
		major, _ = strconv.Atoi(m[1])
		return "chrome", major
	}
	return "chrome", DefaultChromeMajor
}

// Supported reports whether lmw has a TLS fingerprint for the User-Agent's
// browser. Only Chrome-based browsers and Firefox are supported; claiming to
// be another browser with a Chrome fingerprint would be inconsistent.
func (i Identity) Supported() bool {
	return chromeVersion.MatchString(i.UserAgent) || firefoxVersion.MatchString(i.UserAgent)
}

// Load reads a saved identity, or returns the default one if none was saved.
func Load(path string) (Identity, error) {
	raw, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return Default(runtime.GOOS), nil
	}
	if err != nil {
		return Identity{}, err
	}
	var id Identity
	if err := json.Unmarshal(raw, &id); err != nil {
		return Identity{}, fmt.Errorf("%s is not a valid identity file: %w", path, err)
	}
	if id.UserAgent == "" {
		return Identity{}, fmt.Errorf("%s has no user agent", path)
	}
	return id, nil
}

// Save writes the identity so later commands use it.
func Save(path string, id Identity) error {
	raw, err := json.MarshalIndent(id, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o600)
}

// Reset deletes a saved identity so the default is used again.
func Reset(path string) error {
	err := os.Remove(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	return err
}

func platformName(goos string) string {
	switch goos {
	case "windows":
		return "Windows"
	case "darwin":
		return "macOS"
	default:
		return "Linux"
	}
}
