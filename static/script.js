
let selectedRating = 0;
let requestNumber = 0;

const starButtons = document.querySelectorAll(".stars button");
const ratingText = document.getElementById("ratingText");
const feedback = document.getElementById("feedback");
const generateButton = document.getElementById("generate");
const statusText = document.getElementById("status");
const result = document.getElementById("result");
const reviewText = document.getElementById("reviewText");
const copyButton = document.getElementById("copy");
const googleLink = document.getElementById("googleLink");

const ratingLabels = {
    1: "1 star selected",
    2: "2 stars selected",
    3: "3 stars selected",
    4: "4 stars selected",
    5: "5 stars selected"
};

function showReview(text, isFallback = false) {
    reviewText.value = text;
    result.hidden = false;

    googleLink.hidden = !GOOGLE_REVIEW_URL;

    if (GOOGLE_REVIEW_URL) {
        googleLink.href = GOOGLE_REVIEW_URL;
    }

    statusText.textContent = isFallback
        ? "Basic draft shown. AI is unavailable. Please edit it to match your real experience."
        : "Your AI review draft is ready. Please check it before posting.";
}

function fallbackReview(rating) {
    const drafts = {
        1: `My experience at ${document.querySelector("h1").textContent} was not satisfactory. I hope there will be improvements.`,
        2: `My experience at ${document.querySelector("h1").textContent} could have been better. There is room for improvement.`,
        3: `My experience at ${document.querySelector("h1").textContent} was average overall.`,
        4: `I had a good overall experience at ${document.querySelector("h1").textContent}.`,
        5: `I had a very positive overall experience at ${document.querySelector("h1").textContent}.`
    };

    return drafts[rating];
}

async function generateReview() {
    const currentRequest = ++requestNumber;
    generateButton.disabled = true;
    statusText.textContent = "Creating your review draft...";
    result.hidden = true;

    try {
        const response = await fetch("/api/generate-review", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                slug: BUSINESS_SLUG,
                rating: selectedRating,
                feedback: feedback.value.trim()
            })
        });

        const data = await response.json();

        if (currentRequest !== requestNumber) return;

        if (!response.ok) {
            throw new Error(data.error || "AI generation failed.");
        }

        showReview(data.review);

    } catch (error) {
        if (currentRequest !== requestNumber) return;

        console.error("Review generation error:", error);

        // Still show a basic draft if the AI service is unavailable.
        showReview(fallbackReview(selectedRating), true);

    } finally {
        if (currentRequest === requestNumber) {
            generateButton.disabled = false;
        }
    }
}

starButtons.forEach(button => {
    button.addEventListener("click", () => {
        selectedRating = Number(button.dataset.rating);

        starButtons.forEach(star => {
            star.classList.toggle(
                "active",
                Number(star.dataset.rating) <= selectedRating
            );
        });

        ratingText.textContent = ratingLabels[selectedRating];

        // Automatically generate a draft when a star is selected.
        generateReview();
    });
});

// Optional: update the draft when the customer finishes typing feedback.
feedback.addEventListener("change", () => {
    if (selectedRating > 0) {
        generateReview();
    }
});

// Keep the button as an optional way to generate again.
generateButton.addEventListener("click", () => {
    if (!selectedRating) {
        statusText.textContent = "Please select a star rating.";
        return;
    }

    generateReview();
});
copyButton.addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText(reviewText.value);

        copyButton.textContent = "Copied! ✓";

        setTimeout(() => {
            copyButton.textContent = "Copy Review";
        }, 2000);
    } catch {
        reviewText.focus();
        reviewText.select();
        statusText.textContent =
            "Press Ctrl+C to copy your review.";
    }
});
const copyAndOpenButton = document.getElementById("copyAndOpen");

copyAndOpenButton.addEventListener("click", async () => {
    if (!GOOGLE_REVIEW_URL) {
        statusText.textContent = "Google review link is not configured.";
        return;
    }

    try {
        await navigator.clipboard.writeText(reviewText.value);

        // Open Google only after the customer clicks the button.
        window.open(GOOGLE_REVIEW_URL, "_blank", "noopener");

        statusText.textContent =
            "Review copied! Paste it into Google and submit.";
    } catch (error) {
        statusText.textContent =
            "Copy failed. Please select and copy the review manually.";
    }
});