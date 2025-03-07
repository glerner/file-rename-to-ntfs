# Title Case Style Guide

This document serves as a companion to the README.md, providing detailed information about title case capitalization rules used in the File Renamer tool.

## Common Style Guides for Title Capitalization

The File Renamer tool follows standard title case conventions based on established style guides. Here's how different style guides handle capitalization:

### [Chicago Manual of Style (CMOS)](https://www.chicagomanualofstyle.org/)
- Capitalize the first and last words
- Capitalize all "major" words (nouns, verbs, adjectives, adverbs, and pronouns)
- Lowercase articles (a, an, the), coordinating conjunctions (and, but, for, nor, or, so, yet), and prepositions of fewer than five letters (at, by, for, in, of, off, on, out, to, up)
- Capitalize prepositions of five or more letters (about, above, across, after, against, among, around, because, before, behind, below, beneath, beside, between, beyond, during, except, inside, outside, through, toward, under, underneath, until, within, without)

### [APA Style](https://apastyle.apa.org/)
- Capitalize the first word, the first word after a colon or em dash, and proper nouns
- Capitalize all words of four letters or more
- Words with three or fewer letters are generally lowercase unless they are the first word in the title or subtitle, or the first word after a colon or em dash

### [MLA Style](https://style.mla.org/)
- Capitalize the first and last words
- Capitalize all principal words (nouns, pronouns, verbs, adjectives, adverbs, and subordinating conjunctions)
- Lowercase articles (a, an, the), coordinating conjunctions (and, but, for, nor, or, so, yet), prepositions, and the "to" in infinitives

### [AP Style (Associated Press)](https://www.apstylebook.com/)
- Capitalize all words with four or more letters
- Capitalize important words, including prepositions and conjunctions of four or more letters
- Capitalize all verbs (including short ones like "is")
- Lowercase articles (a, an, the), coordinating conjunctions (and, but, for, nor, or, so, yet), and prepositions of three or fewer letters

## Examples of Capitalization Rules

### Example with "no"
- Chicago/MLA: "There Is No Place Like Home" (capitalizes "No" as it's an adverb)
- AP: "There is No Place Like Home" (capitalizes "No" as it's significant)

### Example with "not"
- Chicago/MLA: "Not All Who Wander Are Lost" (capitalizes "Not" as first word and it's an adverb)
- AP: "Not All Who Wander Are Lost" (capitalizes "Not" as first word and it's significant)

### Example with prepositions
- Chicago/MLA: "The Girl with the Dragon Tattoo" ("with" is lowercase as it's a short preposition)
- AP: "The Girl With the Dragon Tattoo" ("With" is capitalized as it's significant)

## Asking About Capitalization Rules

For additional reference, you may find these online title case converters helpful:
- [Capitalize My Title](https://capitalizemytitle.com/) (supports multiple style guides)
- [Title Case Converter](https://titlecaseconverter.com/)
- [Headline Capitalization](https://headlinecapitalization.com/)

If you're unsure about how a specific word should be capitalized in file names, you can ask questions like:

- "Should [word] be capitalized in title case?"
- "Is [word] typically lowercase or uppercase in title case?"
- "According to standard style guides, how should [word] be formatted in titles?"

Example prompt: "In the filename 'The Man With No Name.pdf', should 'with' and 'no' be capitalized according to standard title case rules?"

## File Renamer's Approach

The File Renamer tool primarily follows the [Chicago Manual of Style](https://www.chicagomanualofstyle.org/) for title capitalization, with some adaptations for file naming conventions. The `LOWERCASE_WORDS` set in the code defines which words should remain lowercase when they appear in the middle of a title (not as the first or last word).

To modify which words should be lowercase in your file names, you can edit the `LOWERCASE_WORDS` set in the `file_renamer.py` file.
