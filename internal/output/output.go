// Package output formats results for the terminal.
package output

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"unicode/utf8"

	"golang.org/x/term"

	"github.com/MarcZX100/LinkedinMechaWarrior/internal/api"
)

const (
	maxWidth     = 100
	previewLines = 6
)

// JSON writes v as indented JSON.
func JSON(w io.Writer, v any) error {
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	return enc.Encode(v)
}

// Width is the terminal width, capped for readability.
func Width() int {
	if width, _, err := term.GetSize(int(os.Stdout.Fd())); err == nil && width > 20 && width < maxWidth {
		return width
	}
	return maxWidth
}

// Wrap breaks text into lines of at most width characters, keeping paragraphs.
func Wrap(text string, width int, indent string) []string {
	var lines []string
	avail := width - utf8.RuneCountInString(indent)
	for _, paragraph := range strings.Split(text, "\n") {
		words := strings.Fields(paragraph)
		if len(words) == 0 {
			lines = append(lines, "")
			continue
		}
		line := words[0]
		for _, word := range words[1:] {
			if utf8.RuneCountInString(line)+1+utf8.RuneCountInString(word) > avail {
				lines = append(lines, indent+line)
				line = word
				continue
			}
			line += " " + word
		}
		lines = append(lines, indent+line)
	}
	return lines
}

// Profile formats a profile.
func Profile(p api.Profile) string {
	lines := []string{p.Name}
	if p.Headline != "" {
		lines = append(lines, Wrap(p.Headline, Width(), "")...)
	}
	if p.URL != "" {
		lines = append(lines, p.URL)
	}
	return strings.Join(lines, "\n")
}

// FeedPost formats a feed post; full disables truncation of long texts.
func FeedPost(p api.FeedPost, full bool) string {
	width := Width()
	title := firstNonEmpty(p.Author, "(unknown author)")
	if p.Age != "" {
		title += " · " + p.Age
	}
	if p.Promoted {
		title += " · promoted"
	}
	lines := []string{title}
	if p.AuthorHeadline != "" {
		lines = append(lines, truncate(p.AuthorHeadline, width))
	}
	if p.Context != "" {
		lines = append(lines, "("+p.Context+")")
	}
	if p.ResharedAuthor != "" {
		lines = append(lines, "Reposting "+p.ResharedAuthor)
	}
	if p.Text != "" {
		body := Wrap(p.Text, width, "  ")
		if !full && len(body) > previewLines {
			body = append(body[:previewLines], "  … (use --full to see everything)")
		}
		lines = append(lines, "")
		lines = append(lines, body...)
	}

	var stats []string
	for _, s := range []struct {
		n     *int
		label string
	}{{p.Reactions, "reactions"}, {p.Comments, "comments"}, {p.Reposts, "reposts"}} {
		if s.n != nil {
			stats = append(stats, fmt.Sprintf("%d %s", *s.n, s.label))
		}
	}
	footer := strings.Join(stats, " · ")
	if p.URL != "" {
		footer = strings.TrimSpace(footer + "   " + p.URL)
	}
	if footer != "" {
		lines = append(lines, "", footer)
	}
	return strings.Join(lines, "\n")
}

// PostPreview frames a post with its length.
func PostPreview(text string) string {
	separator := strings.Repeat("-", min(Width(), 60))
	return fmt.Sprintf("%s\n%s\n%s\n%d characters", separator, text, separator, utf8.RuneCountInString(text))
}

func truncate(text string, width int) string {
	if utf8.RuneCountInString(text) <= width {
		return text
	}
	runes := []rune(text)
	return string(runes[:width-1]) + "…"
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}
