import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from db.utils import get_stats_periode, get_top_produits, get_evolution_ca

def show_dashboard():
    # Stats en haut
    col1, col2, col3, col4 = st.columns(4)
    
    stats = get_stats_periode(datetime.now() - timedelta(days=30), datetime.now())
    
    with col1:
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-title">Ventes</div>
                <div class="stat-value">{stats['nb_ventes']}</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-title">CA</div>
                <div class="stat-value">{stats['ca_total']:.0f}€</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-title">Produits</div>
                <div class="stat-value">{stats['nb_produits']}</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-title">Clients</div>
                <div class="stat-value">{stats['nb_clients']}</div>
            </div>
        """, unsafe_allow_html=True)
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    with col1:
        df_evolution = get_evolution_ca(30)
        if not df_evolution.empty:
            fig = px.line(df_evolution, x='Date', y='CA')
            fig.update_layout(
                margin=dict(l=20, r=20, t=30, b=20),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        df_top = get_top_produits(5)
        if not df_top.empty:
            fig = px.bar(df_top, x='Produit', y='Quantite_vendue')
            fig.update_layout(
                margin=dict(l=20, r=20, t=30, b=20),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
            
