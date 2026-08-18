import math

import numpy as np
import pandas as pd
import streamlit as st


def render(ctx):
    pid = ctx.pid
    st.header(ctx.STORY["levels"][5])
    ctx.show_youtube_resources("level_5")
    ctx.show_level_progress(pid, 5)
    st.write("Airport security workload depends on how many passengers arrive and how long each one takes.")
    st.info("A fixed model gives one answer. A random simulation gives many possible answers, so you can see risk.")

    prediction = st.radio(
        ctx.content_get(
            "level_copy.level_5_prediction",
            "Before you try it: as the number of simulation runs grows, what do you think happens to the shape of the results?",
        ),
        ["It gets steadier and more stable", "It gets more random each time", "It stays exactly the same shape no matter what", "It stops being useful"],
        index=None,
        key="l5_prediction",
    )
    if prediction:
        st.caption(f"Prediction recorded: {prediction}")

    arrivals = st.slider("Average arrivals / 10 min", 2, 20, 8)
    service = st.slider("Average service time (min)", 0.5, 4.0, 1.5, 0.1)
    runs = st.selectbox("Monte Carlo runs", options=[10, 100, 1000, 10000], index=2)
    st.caption("More runs make results steadier, but uncertainty is still there.")

    rng = np.random.default_rng(42)
    workloads = []
    for _ in range(runs):
        count = rng.poisson(arrivals)
        if count == 0:
            workloads.append(0.0)
        else:
            workloads.append(rng.exponential(service, count).sum())
    workloads = np.array(workloads)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Estimated mean", f"{workloads.mean():.2f}")
    col_b.metric("Std. deviation", f"{workloads.std(ddof=1):.2f}" if runs > 1 else "-")
    col_c.metric("95th percentile", f"{np.percentile(workloads, 95):.2f}")
    st.caption("95th percentile: about 95% of runs are at or below this value.")

    hist = np.histogram(workloads, bins=min(30, max(5, int(math.sqrt(runs)))))
    st.bar_chart(pd.DataFrame({"Frequency": hist[0]}, index=np.round(hist[1][:-1], 1)))
    st.caption("This chart shows the possible workload totals from many runs.")

    observed = st.radio(
        ctx.content_get("level_copy.level_5_observe", "Did that match what you expected? Try changing the number of runs above to compare."),
        ["Yes", "No", "I am not sure"],
        index=None,
        key="l5_observe",
    )
    if observed:
        st.caption(f"Observation recorded: {observed}")

    st.subheader("Question 1")
    q1 = ctx.answer_radio(
        "What usually happens to a **Monte Carlo estimate** as the **number of runs** increases?",
        [
            "It generally becomes more stable",
            "It always becomes larger",
            "It becomes fixed after 100 runs",
            "It removes the need to model variation",
        ],
        key="l5q1",
    )
    ctx.show_challenge_acknowledgement(pid, "L5_STABILITY")
    if st.button("Submit answer", key="l5submit1"):
        ctx.score_answer(
            pid,
            5,
            "L5_STABILITY",
            q1,
            q1 == "It generally becomes more stable",
            45,
            correct_answer="It generally becomes more stable",
            explanation="More runs average out random noise.",
        )

    st.subheader("Question 2")
    q2 = ctx.answer_radio(
        "Why run **Monte Carlo** many times instead of using **one random simulation**?",
        [
            "To estimate possible outcomes and their chances",
            "To eliminate all uncertainty",
            "To guarantee the maximum possible result",
            "To make every run identical",
        ],
        key="l5q2",
    )
    ctx.show_challenge_acknowledgement(pid, "L5_PURPOSE")
    if st.button("Submit final answer", key="l5submit2"):
        ctx.score_answer(
            pid,
            5,
            "L5_PURPOSE",
            q2,
            q2 == "To estimate possible outcomes and their chances",
            45,
            correct_answer="To estimate possible outcomes and their chances",
            explanation="Monte Carlo repeats random simulations to show what could happen.",
        )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 5):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L5_BONUS")
        q3 = ctx.answer_radio(
            "Which method can make a **Monte Carlo estimate** more **precise**?",
            [
                "A method to get more precise estimates with fewer runs",
                "A method that guarantees zero error",
                "A method that removes the need for randomness",
                "A method that always chooses the largest outcome",
            ],
            key="l5q3",
        )
        if st.button("Submit bonus answer", key="l5submit3"):
            ctx.score_answer(
                pid,
                5,
                "L5_BONUS",
                q3,
                q3 == "A method to get more precise estimates with fewer runs",
                45,
                correct_answer="A method to get more precise estimates with fewer runs",
                explanation="Variance reduction lowers simulation noise.",
            )
    else:
        st.caption("Unlocks if you miss a question above.")

    ctx.show_boss_progress(ctx.xp)
    if ctx.xp >= ctx.PERFECT_SCORE:
        st.markdown(ctx.STORY["epilogue"])
    ctx.show_next_button()
