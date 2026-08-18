import numpy as np
import pandas as pd
import streamlit as st


def render(ctx):
    pid = ctx.pid
    st.header(ctx.STORY["levels"][4])
    ctx.show_youtube_resources("level_4")
    ctx.show_level_progress(pid, 4)
    st.write(
        "An airport wants to model passengers arriving at security. Use Poisson for the number of arrivals "
        "and Exponential for the time between arrivals."
    )

    prediction = st.radio(
        ctx.content_get(
            "level_copy.level_4_prediction",
            "Before you try it: if the average arrival rate doubles, what do you think happens to the average wait between passengers?",
        ),
        ["It gets longer", "It gets shorter", "It stays the same", "There's no relationship"],
        index=None,
        key="l4_prediction",
    )
    if prediction:
        st.caption(f"Prediction recorded: {prediction}")

    rate = st.slider("Average passengers arriving per 10 minutes", 1, 20, 5)
    mean_wait = 10 / rate
    st.metric("Estimated average wait time", f"{mean_wait:.2f} min")
    st.caption("Mean wait time = time interval / arrival rate. More arrivals means shorter waits.")
    np.random.seed(11)
    counts = np.random.poisson(rate, 1000)
    values, freq = np.unique(counts, return_counts=True)
    st.bar_chart(pd.DataFrame({"Frequency": freq}, index=values))
    st.caption("This chart shows passenger counts in 10-minute blocks.")

    observed = st.radio(
        ctx.content_get("level_copy.level_4_observe", "Did that match what you expected?"),
        ["Yes", "No", "I am not sure"],
        index=None,
        key="l4_observe",
    )
    if observed:
        st.caption(f"Observation recorded: {observed}")

    st.subheader("Question 1")
    q1 = ctx.answer_radio(
        "Which distribution models the **number of passengers** arriving in a **fixed time**?",
        ["Poisson", "Exponential", "Normal", "Bernoulli"],
        key="l4q1",
    )
    ctx.show_challenge_acknowledgement(pid, "L4_POISSON")
    ctx.show_optional_hint("L4_POISSON", "You are counting how many passengers arrive during a fixed 10-minute block.")
    if st.button("Lock count answer", key="l4submit1"):
        ctx.score_answer(
            pid,
            4,
            "L4_POISSON",
            q1,
            q1 == "Poisson",
            35,
            correct_answer="Poisson",
            explanation="Poisson models how many events happen in a fixed time.",
        )

    st.subheader("Question 2")
    q2 = ctx.answer_radio(
        "Which distribution models the **time until the next passenger** arrives?",
        ["Binomial", "Exponential", "Uniform", "Poisson"],
        key="l4q2",
    )
    ctx.show_challenge_acknowledgement(pid, "L4_EXP")
    ctx.show_optional_hint("L4_EXP", "You are measuring the gap in time before one single passenger shows up next.")
    if st.button("Lock waiting-time answer", key="l4submit2"):
        ctx.score_answer(
            pid,
            4,
            "L4_EXP",
            q2,
            q2 == "Exponential",
            35,
            correct_answer="Exponential",
            explanation="Exponential models the wait until the next event.",
        )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 4):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L4_BONUS")
        q3 = ctx.answer_radio(
            "If the **average arrival rate doubles**, what happens to the **average wait time**?",
            ["It is halved", "It doubles", "It stays the same", "It becomes negative"],
            key="l4q3",
        )
        if st.button("Lock bonus answer", key="l4submit3"):
            ctx.score_answer(
                pid,
                4,
                "L4_BONUS",
                q3,
                q3 == "It is halved",
                35,
                correct_answer="It is halved",
                explanation="When arrivals happen twice as often, the average wait is cut in half.",
            )
    else:
        st.caption("Unlocks if you miss a question above.")
    ctx.show_next_button()
